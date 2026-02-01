"""
Weekly synthesizer for the Personal Activity Intelligence System.

Orchestrates the weekly synthesis pipeline: for each active project,
gathers activity logs, README content, related project context, and
technology information, then sends it all to the AI for higher-level
synthesis to produce updated project READMEs and refreshed activity logs.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default path for projects configuration
DEFAULT_PROJECTS_CONFIG = "config/projects.json"


class WeeklySynthesizer:
    """Orchestrates weekly synthesis of project activity.

    For each active project, the synthesizer:
    1. Reads the current activity-log.md from Obsidian
    2. Reads the current README.md from Obsidian
    3. Gathers related projects and technologies from Neo4j
    4. Sends all context to the AI for weekly synthesis
    5. Updates the project README.md with AI-generated content
    6. Regenerates the activity-log.md with the last 7 days of data

    Attributes:
        sqlite_manager: SQLite database manager instance.
        graph_manager: Neo4j graph database manager instance.
        ai_client: AI client for weekly synthesis.
        obsidian_writer: Writer for Obsidian vault files.
    """

    def __init__(
        self,
        sqlite_manager,
        graph_manager,
        ai_client,
        obsidian_writer,
    ) -> None:
        """Initialize the WeeklySynthesizer.

        Args:
            sqlite_manager: SQLite database manager for querying activity data.
            graph_manager: Neo4j graph manager for project relationships.
            ai_client: AI client with synthesize_weekly() method.
            obsidian_writer: Writer for creating/updating Obsidian vault files.
        """
        self.sqlite_manager = sqlite_manager
        self.graph_manager = graph_manager
        self.ai_client = ai_client
        self.obsidian_writer = obsidian_writer
        logger.info("WeeklySynthesizer initialized")

    def synthesize(self) -> dict[str, Any]:
        """Run the weekly synthesis pipeline for all active projects.

        Iterates over all active projects (from Neo4j or config/projects.json),
        gathers context for each, sends to AI for synthesis, and updates
        Obsidian vault files.

        Returns:
            A summary dict with keys:
            - projects_synthesized (int): Number of projects processed.
            - readmes_updated (list[str]): Project names with updated READMEs.
            - logs_regenerated (list[str]): Project names with regenerated logs.
            - errors (list[str]): Any error messages encountered.
        """
        logger.info("Starting weekly synthesis pipeline")

        summary: dict[str, Any] = {
            "projects_synthesized": 0,
            "readmes_updated": [],
            "logs_regenerated": [],
            "errors": [],
        }

        # Get active projects from Neo4j first, fall back to config file
        projects = self._get_active_projects()

        if not projects:
            logger.info("No active projects found for weekly synthesis")
            return summary

        logger.info("Found %d active projects for synthesis", len(projects))

        for project in projects:
            project_name = project.get("name", "")
            if not project_name:
                continue

            logger.info("Synthesizing project: %s", project_name)

            try:
                self._synthesize_project(project_name, summary)
                summary["projects_synthesized"] += 1
            except Exception as e:
                error_msg = (
                    f"Error synthesizing project {project_name}: {str(e)}"
                )
                logger.error(error_msg)
                summary["errors"].append(error_msg)

        logger.info(
            "Weekly synthesis complete: %d projects synthesized, "
            "%d READMEs updated, %d logs regenerated, %d errors",
            summary["projects_synthesized"],
            len(summary["readmes_updated"]),
            len(summary["logs_regenerated"]),
            len(summary["errors"]),
        )

        return summary

    def _synthesize_project(
        self, project_name: str, summary: dict[str, Any]
    ) -> None:
        """Synthesize a single project's weekly summary.

        Gathers all context, sends to AI, and applies results.

        Args:
            project_name: The name of the project to synthesize.
            summary: The running summary dict to update with results.
        """
        # Read current activity log
        activity_log = self.obsidian_writer.read_file(
            project_name, "activity-log.md"
        )
        if activity_log is None:
            activity_log = ""
            logger.debug(
                "No existing activity-log.md for project: %s", project_name
            )

        # Read current README
        readme_content = self.obsidian_writer.read_file(
            project_name, "README.md"
        )
        if readme_content is None:
            readme_content = ""
            logger.debug(
                "No existing README.md for project: %s", project_name
            )

        # Get related projects from Neo4j
        related_projects = self._get_related_projects(project_name)

        # Get technologies from Neo4j
        technologies = self._get_project_technologies(project_name)

        # Send to AI for synthesis
        logger.debug(
            "Sending project %s to AI for weekly synthesis "
            "(activity_log: %d chars, readme: %d chars, "
            "%d related projects, %d technologies)",
            project_name,
            len(activity_log),
            len(readme_content),
            len(related_projects),
            len(technologies),
        )

        try:
            ai_response = self.ai_client.synthesize_weekly(
                project_name=project_name,
                activity_log=activity_log,
                readme_content=readme_content,
                related_projects=", ".join(related_projects),
                technologies=", ".join(technologies),
            )

            # The AI returns the updated README content as a string
            result = {"readme": ai_response}

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse AI synthesis response for %s: %s",
                project_name,
                str(e),
            )
            return
        except Exception as e:
            logger.error(
                "AI synthesis failed for project %s: %s",
                project_name,
                str(e),
            )
            return

        # Update README.md with AI-generated content
        new_readme = result.get("readme", "")
        if new_readme:
            try:
                self.obsidian_writer.write_file(
                    project_name, "README.md", new_readme
                )
                summary["readmes_updated"].append(project_name)
                logger.info("Updated README.md for project: %s", project_name)
            except Exception as e:
                logger.error(
                    "Error writing README for %s: %s", project_name, str(e)
                )

        # Regenerate activity-log.md from the database (last 7 days)
        try:
            self._regenerate_activity_log(project_name)
            summary["logs_regenerated"].append(project_name)
            logger.info(
                "Regenerated activity-log.md for project: %s", project_name
            )
        except Exception as e:
            logger.error(
                "Error regenerating activity log for %s: %s",
                project_name,
                str(e),
            )

    def _get_active_projects(self) -> list[dict]:
        """Get active projects from Neo4j, with fallback to config file.

        Tries Neo4j first. If that fails or returns empty, falls back
        to reading config/projects.json.

        Returns:
            List of project dicts with at least a 'name' key.
        """
        # Try Neo4j first
        try:
            projects = self.graph_manager.get_active_projects()
            if projects:
                return projects
        except Exception as e:
            logger.warning(
                "Could not fetch projects from Neo4j, "
                "falling back to config file: %s",
                str(e),
            )

        # Fall back to config/projects.json
        return self._load_projects_from_config()

    def _load_projects_from_config(self) -> list[dict]:
        """Load projects from the config/projects.json file.

        Returns:
            List of project dicts, or empty list if file doesn't exist.
        """
        config_path = DEFAULT_PROJECTS_CONFIG
        if not os.path.exists(config_path):
            logger.warning("Projects config file not found: %s", config_path)
            return []

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both list and dict formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return list(data.get("projects", []))
            else:
                logger.warning("Unexpected format in projects config")
                return []

        except Exception as e:
            logger.error("Error loading projects config: %s", str(e))
            return []

    def _get_related_projects(self, project_name: str) -> list[str]:
        """Get names of projects related to the given project from Neo4j.

        Args:
            project_name: The project to find relationships for.

        Returns:
            List of related project name strings.
        """
        try:
            results = self.graph_manager.get_related_projects(project_name)
            # Extract just the names from the project dicts
            return [p.get("name", "") for p in results if isinstance(p, dict)]
        except Exception as e:
            logger.error(
                "Error fetching related projects for %s: %s",
                project_name,
                str(e),
            )
            return []

    def _get_project_technologies(self, project_name: str) -> list[str]:
        """Get technology names associated with a project from Neo4j.

        Args:
            project_name: The project to get technologies for.

        Returns:
            List of technology name strings.
        """
        try:
            return self.graph_manager.get_project_technologies(project_name)
        except Exception as e:
            logger.error(
                "Error fetching technologies for %s: %s",
                project_name,
                str(e),
            )
            return []

    def _regenerate_activity_log(self, project_name: str) -> None:
        """Regenerate the activity-log.md for a project from the database.

        Queries the last 7 days of activities and writes a fresh
        activity log to Obsidian.

        Args:
            project_name: The project to regenerate the log for.
        """
        seven_days_ago = (
            datetime.utcnow() - timedelta(days=7)
        ).isoformat()

        try:
            activities = self.sqlite_manager.query(
                """
                SELECT e.timestamp, e.source, e.event_type, e.data,
                       e.url, e.title, s.start_time, s.end_time
                FROM events e
                LEFT JOIN sessions s ON e.session_id = s.id
                WHERE e.timestamp >= ?
                ORDER BY e.timestamp ASC
                """,
                (seven_days_ago,),
            )

            # Build activity log content
            if not activities:
                content = f"# Activity Log - {project_name}\n\nNo activity in the last 7 days.\n"
            else:
                lines = [f"# Activity Log - {project_name}\n"]
                current_date = None

                for activity in activities:
                    timestamp = activity.get("timestamp", "")
                    date_str = timestamp[:10] if len(timestamp) >= 10 else timestamp

                    if date_str != current_date:
                        current_date = date_str
                        lines.append(f"\n## {current_date}\n")

                    source = activity.get("source", "")
                    event_type = activity.get("event_type", "")
                    data = activity.get("data", "")
                    title = activity.get("title", "")

                    event_desc = title if title else data
                    if isinstance(event_desc, str) and len(event_desc) > 200:
                        event_desc = event_desc[:200] + "..."

                    lines.append(
                        f"- {timestamp} ({source}/{event_type}) {event_desc}"
                    )

                content = "\n".join(lines) + "\n"

            self.obsidian_writer.write_file(
                project_name, "activity-log.md", content
            )

        except Exception as e:
            logger.error(
                "Error regenerating activity log for %s: %s",
                project_name,
                str(e),
            )
            raise
