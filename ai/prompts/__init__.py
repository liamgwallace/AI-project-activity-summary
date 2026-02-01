"""Prompt templates for AI tasks.

Each module exports a single prompt template string used by
:class:`ai.langchain_client.AIClient`.
"""

from ai.prompts.daily_process import DAILY_PROCESS_PROMPT
from ai.prompts.summarize_page import SUMMARIZE_PAGE_PROMPT
from ai.prompts.weekly_synthesis import WEEKLY_SYNTHESIS_PROMPT

__all__ = [
    "DAILY_PROCESS_PROMPT",
    "SUMMARIZE_PAGE_PROMPT",
    "WEEKLY_SYNTHESIS_PROMPT",
]
