"""
Daily processor for the Personal Activity Intelligence System.

Orchestrates the daily AI processing pipeline: fetches unprocessed sessions,
builds context from events and webpage summaries, sends to AI for analysis,
and applies results to Neo4j (projects, activities) and Obsidian (folders,
activity logs, tweet drafts).
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from config import settings
from utils.helpers import truncate, chunk_text, format_datetime

logger = logging.getLogger(__name__)


class DailyProcessor:
    """Orchestrates the daily AI processing of activity sessions.

    For each unprocessed session, the processor:
    1. Retrieves all events in the session
    2. Enriches browser events with cached webpage summaries
    3. Builds a chronological text representation
    4. Gathers project and technology context from Neo4j
    5. Sends to the AI for analysis
    6. Applies results: creates/updates projects, activities, tweet drafts
    7. Marks the session as processed

    Attributes:
        sqlite_manager: SQLite database manager instance.
        graph_manager: Neo4j graph database manager instance.
        ai_client: AI client for processing sessions.
        obsidian_writer: Writer for Obsidian vault files.
        cache_manager: Webpage summary cache manager.
        max_context_chars: Maximum characters for AI context window.
    """

    def __init__(
        self,
        sqlite_manager,
        graph_manager,
        ai_client,
        obsidian_writer,
        cache_manager,
    ) -> None:
        """Initialize the DailyProcessor.

        Args:
            sqlite_manager: SQLite database manager for events and sessions.
            graph_manager: Neo4j graph manager for projects and relationships.
            ai_client: AI client with process_daily_session() method.
            obsidian_writer: Writer for creating/updating Obsidian vault files.
            cache_manager: CacheManager instance for webpage summaries.
        """
        self.sqlite_manager = sqlite_manager
        self.graph_manager = graph_manager
        self.ai_client = ai_client
        self.obsidian_writer = obsidian_writer
        self.cache_manager = cache_manager
        self.max_context_chars = getattr(settings, "MAX_CONTEXT_CHARS", 50000)
        logger.info("DailyProcessor initialized")

    def process(self) -> dict[str, Any]:
        """Run the daily processing pipeline.

        Fetches all unprocessed sessions, processes each through the AI,
        applies results to Neo4j and Obsidian, and regenerates activity logs.

        Returns:
            A summary dict with keys:
            - sessions_processed (int): Number of sessions processed.
            - projects_created (list[str]): Names of newly created projects.
            - projects_updated (list[str]): Names of updated projects.
            - tweets_drafted (int): Number of tweet drafts created.
            - errors (list[str]): Any error messages encountered.
        """
        logger.info("Starting daily processing pipeline")

        summary = {
            "sessions_processed": 0,
            "projects_created": [],
            "projects_updated": [],
            "tweets_drafted": 0,
            "errors": [],
        }

        # Get unprocessed sessions
        sessions = self._get_unprocessed_sessions()
        if not sessions:
            logger.info("No unprocessed sessions found")
            return summary

        logger.info("Found %d unprocessed sessions to process", len(sessions))

        # Get context from Neo4j
        active_projects = self._get_active_projects()
        known_technologies = self._get_known_technologies()

        for session in sessions:
            session_id = session["id"]
            logger.info("Processing session: %s", session_id)

            try:
                result = self._process_single_session(
                    session_id=session_id,
                    active_projects=active_projects,
                    known_technologies=known_technologies,
                )

                if result:
                    self._apply_ai_results(result)

                    # Track created and updated projects
                    for project in result.get("projects", []):
                        project_name = project.get("name", "")
                        if project.get("is_new", False):
                            summary["projects_created"].append(project_name)
                        else:
                            summary["projects_updated"].append(project_name)

                    # Track tweet drafts
                    summary["tweets_drafted"] += len(
                        result.get("tweet_drafts", [])
                    )

                # Mark session as processed
                self._mark_session_processed(session_id)
                summary["sessions_processed"] += 1

                logger.info("Successfully processed session: %s", session_id)

            except Exception as e:
                error_msg = f"Error processing session {session_id}: {str(e)}"
                logger.error(error_msg)
                summary["errors"].append(error_msg)

        # After all sessions: regenerate activity logs
        try:
            self._regenerate_activity_logs()
        except Exception as e:
            error_msg = f"Error regenerating activity logs: {str(e)}"
            logger.error(error_msg)
            summary["errors"].append(error_msg)

        logger.info(
            "Daily processing complete: %d sessions, %d projects created, "
            "%d projects updated, %d tweets drafted, %d errors",
            summary["sessions_processed"],
            len(summary["projects_created"]),
            len(summary["projects_updated"]),
            summary["tweets_drafted"],
            len(summary["errors"]),
        )

        return summary

    def _process_single_session(
        self,
        session_id: str,
        active_projects: list[dict],
        known_technologies: list[str],
    ) -> Optional[dict]:
        """Process a single session through the AI pipeline.

        Args:
            session_id: The UUID of the session to process.
            active_projects: List of active project dicts from Neo4j.
            known_technologies: List of known technology names from Neo4j.

        Returns:
            The parsed JSON response from the AI, or None on failure.
        """
        # Get all events in this session
        events = self.sqlite_manager.query(
            """
            SELECT id, timestamp, source, event_type, data, url, title
            FROM events
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )

        if not events:
            logger.warning("No events found for session: %s", session_id)
            return None

        # Build event text with webpage summaries
        event_text = self._build_event_text(events, self.cache_manager)

        # Build project context
        project_names = [p.get("name", "") for p in active_projects]

        # Check if context exceeds max limit and batch if needed
        context_parts = {
            "events": event_text,
            "projects": json.dumps(project_names),
            "technologies": json.dumps(known_technologies),
        }

        total_chars = sum(len(v) for v in context_parts.values())

        if total_chars > self.max_context_chars:
            logger.info(
                "Context size (%d chars) exceeds max (%d chars), batching",
                total_chars,
                self.max_context_chars,
            )
            return self._process_batched(
                event_text=event_text,
                active_projects=project_names,
                known_technologies=known_technologies,
            )

        # Send to AI for processing
        try:
            response = self.ai_client.process_daily_session(
                events=event_text,
                active_projects=json.dumps(project_names),
                known_technologies=json.dumps(known_technologies),
            )
            return response

        except Exception as e:
            logger.error("AI processing failed for session %s: %s", session_id, str(e))
            return None

    def _process_batched(
        self,
        event_text: str,
        active_projects: list[str],
        known_technologies: list[str],
    ) -> Optional[dict]:
        """Process event text in batches when context exceeds max size.

        Splits event text into chunks and processes each separately,
        then merges the results.

        Args:
            event_text: The full event text to split.
            active_projects: List of active project names.
            known_technologies: List of known technology names.

        Returns:
            Merged results dict, or None on failure.
        """
        # Reserve space for project/tech context
        context_overhead = len(json.dumps(active_projects)) + len(
            json.dumps(known_technologies)
        )
        chunk_max = self.max_context_chars - context_overhead - 1000  # buffer

        if chunk_max < 1000:
            logger.warning("Context overhead too large, using minimum chunk size")
            chunk_max = 1000

        chunks = chunk_text(event_text, chunk_max)
        logger.info("Split event text into %d chunks", len(chunks))

        merged_result: dict[str, Any] = {
            "projects": [],
            "activities": [],
            "notable_moments": [],
            "tweet_drafts": [],
        }

        for i, chunk in enumerate(chunks):
            logger.debug("Processing chunk %d/%d", i + 1, len(chunks))
            try:
                result = self.ai_client.process_daily_session(
                    events=chunk,
                    active_projects=json.dumps(active_projects),
                    known_technologies=json.dumps(known_technologies),
                )

                # Merge results
                for key in merged_result:
                    if key in result and isinstance(result[key], list):
                        merged_result[key].extend(result[key])

            except Exception as e:
                logger.error("Error processing chunk %d: %s", i + 1, str(e))

        return merged_result if any(merged_result.values()) else None

    def _build_event_text(self, events: list[dict], cache_manager) -> str:
        """Build a chronological text representation of events for the AI.

        Each event is formatted as a timestamped line with source, type,
        and relevant data. Browser events with URLs are enriched with
        cached webpage summaries.

        Args:
            events: List of event dicts ordered by timestamp.
            cache_manager: CacheManager instance for webpage summaries.

        Returns:
            A formatted string of all events suitable for AI processing.
        """
        lines: list[str] = []

        for event in events:
            timestamp = event.get("timestamp", "unknown")
            source = event.get("source", "unknown")
            event_type = event.get("event_type", "unknown")
            data = event.get("data", "")
            url = event.get("url", "")
            title = event.get("title", "")

            # Build the base event line
            line = f"[{timestamp}] ({source}/{event_type})"

            if title:
                line += f" {title}"
            if data:
                # Truncate very long data payloads
                data_str = str(data) if not isinstance(data, str) else data
                line += f" - {truncate(data_str, 500)}"

            # Enrich with webpage summary for browser events
            if url and cache_manager:
                summary = cache_manager.get_or_create_summary(url, title)
                if summary:
                    summary_truncated = truncate(summary, 300)
                    line += f"\n  Summary: {summary_truncated}"

            lines.append(line)

        return "\n".join(lines)

    def _apply_ai_results(self, results: dict) -> None:
        """Apply AI processing results to Neo4j and Obsidian.

        Creates or updates projects in Neo4j, creates activity nodes and
        relationships, sets up Obsidian folder structures for new projects,
        and drafts tweets for notable tweetable moments.

        Args:
            results: The parsed AI response dict containing:
                - projects: list of project dicts with name, is_new, etc.
                - activities: list of activity dicts.
                - notable_moments: list of moment dicts with tweetable flag.
                - tweet_drafts: list of tweet draft dicts.
        """
        logger.debug("Applying AI results to Neo4j and Obsidian")

        # Process projects
        for project in results.get("projects", []):
            project_name = project.get("name", "")
            if not project_name:
                continue

            try:
                if project.get("is_new", False):
                    # Create new project in Neo4j
                    self.graph_manager.create_project(
                        name=project_name,
                        description=project.get("description", ""),
                        technologies=project.get("technologies", []),
                        tags=project.get("tags", []),
                    )

                    # Create Obsidian folder structure for new project
                    self.obsidian_writer.create_project_folder(project_name)
                    logger.info("Created new project: %s", project_name)
                else:
                    # Update existing project
                    self.graph_manager.update_project(
                        name=project_name,
                        last_activity=datetime.utcnow().isoformat(),
                    )
                    logger.debug("Updated project: %s", project_name)

                # Create activity nodes
                for activity in project.get("activities", []):
                    self.graph_manager.create_activity(
                        project_name=project_name,
                        description=activity.get("description", ""),
                        activity_type=activity.get("type", "development"),
                        timestamp=activity.get("timestamp", datetime.utcnow().isoformat()),
                    )

            except Exception as e:
                logger.error(
                    "Error applying results for project %s: %s",
                    project_name,
                    str(e),
                )

        # Process standalone activities (not tied to a project in the result)
        for activity in results.get("activities", []):
            try:
                project_name = activity.get("project", "")
                if project_name:
                    self.graph_manager.create_activity(
                        project_name=project_name,
                        description=activity.get("description", ""),
                        activity_type=activity.get("type", "development"),
                        timestamp=activity.get(
                            "timestamp", datetime.utcnow().isoformat()
                        ),
                    )
            except Exception as e:
                logger.error("Error creating activity: %s", str(e))

        # Process notable moments and create tweet drafts
        for moment in results.get("notable_moments", []):
            if moment.get("tweetable", False):
                try:
                    self.obsidian_writer.write_tweet_draft(
                        description=moment.get("description", ""),
                        tweet_text=moment.get("tweet_text", ""),
                        project_name=moment.get("project", None),
                    )
                    logger.debug(
                        "Created tweet draft for: %s",
                        truncate(moment.get("description", ""), 50),
                    )
                except Exception as e:
                    logger.error("Error creating tweet draft: %s", str(e))

        # Process explicit tweet drafts from AI response
        for draft in results.get("tweet_drafts", []):
            try:
                self.obsidian_writer.write_tweet_draft(
                    description=draft.get("description", ""),
                    tweet_text=draft.get("tweet_text", ""),
                    project_name=draft.get("project", None),
                )
            except Exception as e:
                logger.error("Error creating tweet draft: %s", str(e))

    def _get_unprocessed_sessions(self) -> list[dict]:
        """Fetch all unprocessed sessions from SQLite.

        Returns:
            List of session dicts with processed=0.
        """
        try:
            return self.sqlite_manager.query(
                """
                SELECT id, start_time, end_time, event_count
                FROM sessions
                WHERE processed = 0
                ORDER BY start_time ASC
                """,
            )
        except Exception as e:
            logger.error("Error fetching unprocessed sessions: %s", str(e))
            return []

    def _get_active_projects(self) -> list[dict]:
        """Fetch active projects from Neo4j.

        Returns:
            List of project dicts with name and metadata.
        """
        try:
            return self.graph_manager.get_active_projects()
        except Exception as e:
            logger.error("Error fetching active projects from Neo4j: %s", str(e))
            return []

    def _get_known_technologies(self) -> list[str]:
        """Fetch known technology names from Neo4j.

        Returns:
            List of technology name strings.
        """
        try:
            return self.graph_manager.get_technologies()
        except Exception as e:
            logger.error("Error fetching technologies from Neo4j: %s", str(e))
            return []

    def _mark_session_processed(self, session_id: str) -> None:
        """Mark a session as processed in SQLite.

        Args:
            session_id: The UUID of the session to mark.
        """
        try:
            self.sqlite_manager.execute(
                """
                UPDATE sessions
                SET processed = 1, processed_at = ?
                WHERE id = ?
                """,
                (datetime.utcnow().isoformat(), session_id),
            )
            logger.debug("Marked session %s as processed", session_id)
        except Exception as e:
            logger.error(
                "Error marking session %s as processed: %s",
                session_id,
                str(e),
            )

    def _regenerate_activity_logs(self) -> None:
        """Regenerate activity logs for all active projects.

        Called after all sessions are processed to ensure activity logs
        reflect the latest data.
        """
        logger.info("Regenerating activity logs")

        try:
            active_projects = self._get_active_projects()
            for project in active_projects:
                project_name = project.get("name", "")
                if project_name:
                    self.obsidian_writer.regenerate_activity_log(project_name)
                    logger.debug(
                        "Regenerated activity log for: %s", project_name
                    )
        except Exception as e:
            logger.error("Error regenerating activity logs: %s", str(e))
