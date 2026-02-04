"""
AI processor for activity analysis and weekly synthesis.

Handles interaction with OpenRouter API through LangChain for
processing daily activity batches and generating weekly summaries.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config.settings import get_settings, get_model_config
from storage.database import Database, RawEvent, Activity, Entity, Relationship
from processing.prompts.daily_process import DAILY_PROCESS_PROMPT
from processing.prompts.weekly_synthesis import WEEKLY_SYNTHESIS_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result from processing a batch of events."""
    activities: List[Dict[str, Any]]
    new_projects: List[Dict[str, Any]]
    tweets: List[Dict[str, Any]]
    input_tokens: int
    output_tokens: int
    success: bool = True
    error_message: Optional[str] = None
    new_entities: List[Dict[str, Any]] = field(default_factory=list)
    entity_relationships: List[Dict[str, Any]] = field(default_factory=list)


class AIProcessor:
    """
    Processes activities using AI models through OpenRouter.
    
    Handles daily batch processing and weekly synthesis with
    proper error handling and retry logic.
    """
    
    def __init__(self, model_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AI processor.
        
        Args:
            model_config: Optional custom model configuration.
                         If not provided, uses default from settings.
        """
        self.settings = get_settings()
        
        if model_config is None:
            model_config = get_model_config("default")
        
        self.model_config = model_config
        
        # Initialize LangChain ChatOpenAI with OpenRouter
        # OpenRouter uses OpenAI-compatible API
        api_key = self.settings.openai.api_key
        
        if not api_key:
            logger.error("No OpenAI API key configured")
            raise ValueError("OpenAI API key is required")
        
        # Check if using OpenRouter (different base URL)
        base_url = model_config.get("base_url", "https://api.openai.com/v1")
        if "openrouter" in base_url.lower():
            logger.info("Using OpenRouter API")
        
        self.llm = ChatOpenAI(
            model=model_config.get("model", "gpt-4o-mini"),
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 2000),
            api_key=api_key,
            base_url=base_url if base_url != "https://api.openai.com/v1" else None,
        )
        
        logger.info(
            f"AIProcessor initialized with model: {model_config.get('model')}"
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    def process_batch(
        self,
        events: List[RawEvent],
        existing_projects: Dict[str, Dict[str, Any]],
    ) -> ProcessingResult:
        """
        Process a batch of events into structured activities.
        
        Args:
            events: List of raw events to process
            existing_projects: Dictionary of existing project names and their details
            
        Returns:
            ProcessingResult with activities, new projects, and tweets
        """
        if not events:
            logger.warning("No events to process")
            return ProcessingResult(
                activities=[],
                new_projects=[],
                tweets=[],
                input_tokens=0,
                output_tokens=0,
            )
        
        try:
            # Build the prompt
            prompt = self._build_daily_prompt(events, existing_projects)
            
            # Send to AI
            messages = [
                SystemMessage(content="You are an expert activity analysis system."),
                HumanMessage(content=prompt),
            ]
            
            logger.info(f"Processing {len(events)} events with AI")
            response = self.llm.invoke(messages)
            
            # Estimate tokens (actual counts may vary)
            input_tokens = len(prompt) // 4
            output_tokens = len(response.content) // 4
            
            # Parse the response
            result = self._parse_response(response.content)
            result.input_tokens = input_tokens
            result.output_tokens = output_tokens

            logger.info(
                f"Processed {len(events)} events into "
                f"{len(result.activities)} activities, "
                f"{len(result.new_projects)} new projects, "
                f"{len(result.new_entities)} new entities, "
                f"{len(result.entity_relationships)} relationships"
            )

            # Store entities and relationships (activities will be stored separately)
            if result.new_entities or result.entity_relationships:
                try:
                    self._store_entities_and_relationships(result, {})
                except Exception as store_error:
                    logger.error(f"Error storing entities/relationships: {store_error}")
                    # Don't fail the whole batch if entity storage fails

            # Record token usage
            self._record_usage("daily_process", input_tokens, output_tokens)

            return result
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            return ProcessingResult(
                activities=[],
                new_projects=[],
                tweets=[],
                input_tokens=0,
                output_tokens=0,
                success=False,
                error_message=str(e),
            )
    
    def weekly_synthesis(
        self,
        project_name: str,
        activities: List[Activity],
        current_readme: str,
        project_entities: str = "",
        related_context: str = "",
    ) -> str:
        """
        Generate weekly summary for a project.

        Args:
            project_name: Name of the project
            activities: List of activities from the week
            current_readme: Current README content for context
            project_entities: Entity context for the project (technologies, concepts)
            related_context: Related entities and cross-project context

        Returns:
            Markdown string with weekly summary
        """
        if not activities:
            logger.warning(f"No activities for {project_name} weekly synthesis")
            return f"## Week of {datetime.now().strftime('%b %d, %Y')}\n\nNo recorded activities this week."

        try:
            # Build the prompt with entity context
            prompt = self._build_weekly_prompt(
                project_name=project_name,
                activities=activities,
                current_readme=current_readme,
                project_entities=project_entities,
                related_context=related_context,
            )
            
            # Send to AI
            messages = [
                SystemMessage(content="You are an expert technical writer."),
                HumanMessage(content=prompt),
            ]
            
            logger.info(f"Generating weekly synthesis for {project_name}")
            response = self.llm.invoke(messages)
            
            # Estimate and record token usage
            input_tokens = len(prompt) // 4
            output_tokens = len(response.content) // 4
            self._record_usage("weekly_synthesis", input_tokens, output_tokens)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating weekly synthesis for {project_name}: {e}")
            return f"## Week of {datetime.now().strftime('%b %d, %Y')}\n\nError generating summary: {e}"
    
    def _build_weekly_prompt(
        self,
        project_name: str,
        activities: List[Activity],
        current_readme: str,
        project_entities: str,
        related_context: str,
    ) -> str:
        """
        Build the weekly synthesis prompt from template.

        Args:
            project_name: Name of the project
            activities: List of activities from the week
            current_readme: Current README content for context
            project_entities: Entity context for the project
            related_context: Related entities and cross-project context

        Returns:
            Formatted prompt string
        """
        # Build activities string
        activities_str = ""
        for activity in activities:
            activities_str += f"- [{activity.activity_type}] {activity.description}\n"
            activities_str += f"  Date: {activity.timestamp[:10]}\n"

        # Format the prompt with entity context
        return WEEKLY_SYNTHESIS_PROMPT.format(
            project_name=project_name,
            project_entities=project_entities or "No project entities recorded.",
            related_context=related_context or "No related context available.",
            current_readme=current_readme or "No existing README",
            activities=activities_str,
            date=datetime.now().strftime("%Y-%m-%d"),
        )

    def _format_entities(self, entities: List[Entity]) -> str:
        """Format entity list for prompt."""
        if not entities:
            return "No existing entities."
        
        result = []
        for entity in entities:
            result.append(f"- {entity.name} ({entity.entity_type})")
        return "\n".join(result)
    
    def _format_relationships(self, relationships: List[Relationship]) -> str:
        """Format relationship list for prompt."""
        if not relationships:
            return "No existing relationships."
        
        result = []
        for rel in relationships:
            result.append(f"- {rel.from_type}:{rel.from_id} -> {rel.to_type}:{rel.to_id} ({rel.rel_type})")
        return "\n".join(result)

    def _build_daily_prompt(
        self,
        events: List[RawEvent],
        projects: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Build the daily processing prompt from template.

        Args:
            events: List of raw events
            projects: Dictionary of existing projects

        Returns:
            Formatted prompt string
        """
        # Format existing projects
        projects_str = ""
        if projects:
            for name, details in projects.items():
                projects_str += f"- {name}"
                if details.get("description"):
                    projects_str += f": {details['description']}"
                if details.get("keywords"):
                    projects_str += f" [keywords: {', '.join(details['keywords'])}]"
                projects_str += "\n"
        else:
            projects_str = "No existing projects."

        # Retrieve and format entity context
        try:
            db = Database()
            recent_entities = db.get_recent_entities(days=30, limit=50)
            recent_relationships = db.get_recent_relationships(days=30, limit=30)
            entities_str = self._format_entities(recent_entities)
            relationships_str = self._format_relationships(recent_relationships)
        except Exception as e:
            logger.warning(f"Failed to retrieve entity context: {e}")
            entities_str = "No existing entities."
            relationships_str = "No existing relationships."

        # Format events
        events_str = ""
        for event in events:
            events_str += f"[{event.source}/{event.event_type}] {event.event_time}\n"
            events_str += f"{event.raw_data}\n"
            events_str += "---\n"

        return DAILY_PROCESS_PROMPT.format(
            existing_projects=projects_str,
            existing_entities=entities_str,
            recent_relationships=relationships_str,
            events=events_str,
        )
    
    def _parse_response(self, response: str) -> ProcessingResult:
        """
        Parse AI response into structured result.
        
        Args:
            response: Raw AI response text
            
        Returns:
            ProcessingResult with parsed data
        """
        # Try to extract JSON from response
        # Response might be wrapped in markdown code blocks
        try:
            # Look for JSON in code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)

            return ProcessingResult(
                activities=data.get("activities", []),
                new_projects=data.get("new_projects", []),
                tweets=data.get("tweets", []),
                input_tokens=0,
                output_tokens=0,
                success=True,
                new_entities=data.get("new_entities", []),
                entity_relationships=data.get("entity_relationships", []),
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response content: {response[:500]}...")
            
            # Return empty result with error
            return ProcessingResult(
                activities=[],
                new_projects=[],
                tweets=[],
                input_tokens=0,
                output_tokens=0,
                success=False,
                error_message=f"JSON parse error: {e}",
            )
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return ProcessingResult(
                activities=[],
                new_projects=[],
                tweets=[],
                input_tokens=0,
                output_tokens=0,
                success=False,
                error_message=str(e),
            )
    
    def _store_entities_and_relationships(
        self,
        result: ProcessingResult,
        entity_id_map: Dict[str, int],
    ) -> None:
        """
        Store entities and relationships from processing result.
        
        Args:
            result: ProcessingResult containing entities and relationships
            entity_id_map: Dictionary mapping entity names to IDs
        """
        try:
            db = Database(self.settings.database.path)
            
            # Store new entities
            if result.new_entities:
                logger.info(f"Storing {len(result.new_entities)} entities...")
                for entity_data in result.new_entities:
                    entity_name = entity_data.get("name", "").lower()
                    entity_type = entity_data.get("type", "unknown")
                    display_name = entity_data.get("display_name")
                    metadata = entity_data.get("metadata", {})
                    
                    if entity_name:
                        entity_id = db.get_or_create_entity(
                            name=entity_name,
                            entity_type=entity_type,
                            display_name=display_name,
                            metadata=metadata,
                        )
                        entity_id_map[entity_name] = entity_id
                        logger.debug(f"Stored entity: {entity_name} (type: {entity_type}, id: {entity_id})")
                
                logger.info(f"Successfully stored {len(entity_id_map)} entities")
            
            # Store entity relationships
            if result.entity_relationships and entity_id_map:
                logger.info(f"Storing {len(result.entity_relationships)} entity relationships...")
                for rel in result.entity_relationships:
                    from_entity = rel.get("from_entity", "").lower()
                    to_entity = rel.get("to_entity", "").lower()
                    rel_type = rel.get("type", "related_to")
                    confidence = rel.get("confidence", 1.0)
                    
                    # Get entity IDs (entities must exist in our map)
                    from_id = entity_id_map.get(from_entity)
                    to_id = entity_id_map.get(to_entity)
                    
                    if from_id and to_id:
                        # Determine entity types from the new_entities data
                        from_type = "unknown"
                        to_type = "unknown"
                        for entity_data in result.new_entities:
                            if entity_data.get("name", "").lower() == from_entity:
                                from_type = entity_data.get("type", "unknown")
                            if entity_data.get("name", "").lower() == to_entity:
                                to_type = entity_data.get("type", "unknown")
                        
                        db.create_relationship(
                            from_type=from_type,
                            from_id=from_id,
                            to_type=to_type,
                            to_id=to_id,
                            rel_type=rel_type,
                            confidence=confidence,
                        )
                        logger.debug(f"Stored relationship: {from_entity} -> {to_entity} ({rel_type})")
                
                logger.info(f"Successfully stored entity relationships")
                
        except Exception as e:
            logger.error(f"Error storing entities/relationships: {e}")
            raise

    def _record_usage(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Record token usage in database.
        
        Args:
            operation: Type of operation performed
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        try:
            db = Database()
            
            # Rough cost estimate (varies by model)
            # Using approximate rates for gpt-4o-mini
            input_cost = input_tokens * 0.00000015  # $0.15 per 1M tokens
            output_cost = output_tokens * 0.0000006  # $0.60 per 1M tokens
            total_cost = input_cost + output_cost
            
            db.record_token_usage(
                operation=operation,
                model=self.model_config.get("model", "unknown"),
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                cost_estimate=total_cost,
            )
            
            logger.debug(
                f"Recorded usage: {operation} - "
                f"{input_tokens}+{output_tokens} tokens, "
                f"${total_cost:.4f}"
            )
            
        except Exception as e:
            logger.error(f"Error recording token usage: {e}")
