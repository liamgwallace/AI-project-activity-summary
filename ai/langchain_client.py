"""LangChain + OpenRouter AI client for the Personal Activity Intelligence System.

Provides a unified interface for all AI/LLM operations: webpage summarization,
daily activity processing, and weekly project synthesis.  Each task type is
backed by its own ChatOpenAI instance configured from ``config/models.json``.

Usage::

    from storage.sqlite_manager import SQLiteManager
    from ai.langchain_client import AIClient

    db = SQLiteManager()
    client = AIClient(sqlite_manager=db)
    summary = client.summarize_page(title="Example", content="...")
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ai.chains.structured_output import parse_json_response, validate_daily_output
from ai.prompts.daily_process import DAILY_PROCESS_PROMPT
from ai.prompts.summarize_page import SUMMARIZE_PAGE_PROMPT
from ai.prompts.weekly_synthesis import WEEKLY_SYNTHESIS_PROMPT
from config.settings import settings

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


class AIClient:
    """Central AI client that manages LLM interactions through OpenRouter.

    Loads model configurations from ``config/models.json`` and creates
    separate :class:`ChatOpenAI` instances for each task type.  All API
    calls are logged to SQLite via the provided ``sqlite_manager``.

    Args:
        sqlite_manager: An initialised :class:`SQLiteManager` instance used
            to record token usage and errors for every AI call.
    """

    def __init__(self, sqlite_manager) -> None:
        self.sqlite_manager = sqlite_manager
        self.model_configs: Dict[str, Any] = self._load_model_configs()
        self.models: Dict[str, ChatOpenAI] = {}

        # Pre-create LLM instances for each configured task type
        for task_type, config in self.model_configs.items():
            self.models[task_type] = self._create_llm(task_type, config)

        logger.info(
            "AIClient initialized with %d model configurations: %s",
            len(self.models),
            list(self.models.keys()),
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _load_model_configs() -> Dict[str, Any]:
        """Load model configurations from ``config/models.json``.

        Returns:
            A dictionary mapping task type names to their model configuration.

        Raises:
            FileNotFoundError: If the models.json file is missing.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        config_path = Path(__file__).resolve().parent.parent / "config" / "models.json"
        logger.debug("Loading model configs from %s", config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            configs = json.load(f)

        logger.info("Loaded model configs for task types: %s", list(configs.keys()))
        return configs

    def _create_llm(self, task_type: str, config: Dict[str, Any]) -> ChatOpenAI:
        """Create a ChatOpenAI instance configured for a specific task type.

        Args:
            task_type: The name of the task (used for logging).
            config: Model configuration dictionary from models.json.

        Returns:
            A configured :class:`ChatOpenAI` instance.
        """
        model_name = config.get("model", "anthropic/claude-3-haiku")
        temperature = config.get("temperature", 0.3)
        max_tokens = config.get("max_tokens", 1024)

        llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
        )

        logger.debug(
            "Created LLM for task '%s': model=%s, temperature=%s, max_tokens=%d",
            task_type,
            model_name,
            temperature,
            max_tokens,
        )
        return llm

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_model(self, task_type: str) -> ChatOpenAI:
        """Return the ChatOpenAI instance configured for the given task type.

        Args:
            task_type: One of the keys in ``config/models.json``
                (e.g. ``"summarization"``, ``"daily_processing"``,
                ``"weekly_synthesis"``).

        Returns:
            The corresponding :class:`ChatOpenAI` instance.

        Raises:
            KeyError: If *task_type* is not a recognised task.
        """
        if task_type not in self.models:
            available = list(self.models.keys())
            raise KeyError(
                f"Unknown task type '{task_type}'. Available: {available}"
            )
        return self.models[task_type]

    def summarize_page(self, title: str = "", content: str = "") -> str:
        """Summarize a webpage's content into 1-2 concise paragraphs.

        Args:
            title: The page title.
            content: The extracted text content of the page.

        Returns:
            A short summary string.
        """
        prompt = ChatPromptTemplate.from_template(SUMMARIZE_PAGE_PROMPT)
        chain = prompt | self.get_model("summarization")

        response = self._invoke_with_retry(
            chain=chain,
            input_data={"title": title, "content": content},
            task_type="summarization",
        )
        return response.content

    def process_daily_session(
        self,
        events: str,
        active_projects: str,
        known_technologies: str,
    ) -> dict:
        """Analyse a session of activity and extract structured information.

        Args:
            events: Chronological description of session events.
            active_projects: Context string of currently active projects.
            known_technologies: Context string of known technologies.

        Returns:
            A parsed dictionary matching the daily processing JSON schema.

        Raises:
            ValueError: If the AI response cannot be parsed into valid JSON
                or does not match the expected schema.
        """
        prompt = ChatPromptTemplate.from_template(DAILY_PROCESS_PROMPT)
        chain = prompt | self.get_model("daily_processing")

        response = self._invoke_with_retry(
            chain=chain,
            input_data={
                "events": events,
                "active_projects": active_projects,
                "known_technologies": known_technologies,
            },
            task_type="daily_processing",
        )

        # Parse and validate the structured JSON output
        parsed = parse_json_response(response.content)

        if not validate_daily_output(parsed):
            logger.error(
                "Daily processing output failed validation: %s",
                response.content[:500],
            )
            raise ValueError(
                "AI response did not match expected daily processing schema"
            )

        return parsed

    def synthesize_weekly(
        self,
        project_name: str,
        readme_content: str,
        activity_log: str,
        related_projects: str,
        technologies: str,
    ) -> str:
        """Synthesize weekly progress and update a project README.

        Args:
            project_name: Name of the project being summarised.
            readme_content: Current content of the project's README.
            activity_log: Detailed activity log for the past week.
            related_projects: Comma-separated list of related project names.
            technologies: Comma-separated list of technologies used.

        Returns:
            The complete updated README content as a string.
        """
        prompt = ChatPromptTemplate.from_template(WEEKLY_SYNTHESIS_PROMPT)
        chain = prompt | self.get_model("weekly_synthesis")

        response = self._invoke_with_retry(
            chain=chain,
            input_data={
                "project_name": project_name,
                "readme_content": readme_content,
                "activity_log": activity_log,
                "related_projects": related_projects,
                "technologies": technologies,
            },
            task_type="weekly_synthesis",
        )
        return response.content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invoke_with_retry(
        self,
        chain,
        input_data: Dict[str, Any],
        task_type: str,
    ):
        """Invoke a LangChain chain with exponential-backoff retries.

        On success the token usage is logged.  On final failure the error is
        logged and the exception is re-raised.

        Args:
            chain: The LangChain chain (prompt | llm) to invoke.
            input_data: The template variables to pass to the chain.
            task_type: The task type string for logging purposes.

        Returns:
            The AI message response object.

        Raises:
            Exception: The last exception if all retries are exhausted.
        """
        model_name = self.model_configs.get(task_type, {}).get("model", "unknown")
        last_exception: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            start_time = time.time()
            try:
                response = chain.invoke(input_data)
                duration = time.time() - start_time

                # Extract token usage from response metadata if available
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "response_metadata"):
                    token_usage = response.response_metadata.get(
                        "token_usage", {}
                    )
                    input_tokens = token_usage.get("prompt_tokens", 0)
                    output_tokens = token_usage.get("completion_tokens", 0)

                # Log successful call
                self.sqlite_manager.log_ai_call(
                    task_type=task_type,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_used=model_name,
                    duration_seconds=duration,
                )

                logger.info(
                    "AI call succeeded: task=%s, model=%s, attempt=%d/%d, "
                    "tokens=%d+%d, duration=%.2fs",
                    task_type,
                    model_name,
                    attempt,
                    MAX_RETRIES,
                    input_tokens,
                    output_tokens,
                    duration,
                )
                return response

            except Exception as exc:
                duration = time.time() - start_time
                last_exception = exc
                logger.warning(
                    "AI call failed (attempt %d/%d): task=%s, model=%s, "
                    "error=%s, duration=%.2fs",
                    attempt,
                    MAX_RETRIES,
                    task_type,
                    model_name,
                    str(exc),
                    duration,
                )

                # Log the failed attempt
                self.sqlite_manager.log_ai_call(
                    task_type=task_type,
                    input_tokens=0,
                    output_tokens=0,
                    model_used=model_name,
                    duration_seconds=duration,
                    error=str(exc),
                )

                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.info(
                        "Retrying in %.1f seconds...", backoff
                    )
                    time.sleep(backoff)

        # All retries exhausted
        logger.error(
            "All %d retries exhausted for task=%s, model=%s. Last error: %s",
            MAX_RETRIES,
            task_type,
            model_name,
            str(last_exception),
        )
        raise last_exception
