"""Project updater for the Personal Activity Intelligence System.

Manages auto-creation of new projects detected by AI processing
and updates the config/projects.json configuration file.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import CONFIG_DIR

logger = logging.getLogger(__name__)

PROJECTS_CONFIG_PATH = os.path.join(CONFIG_DIR, "projects.json")


class ProjectUpdater:
    """Manages project configuration and auto-creation of new projects.

    When the AI detects a new project theme, this class:
    1. Creates the project entry in config/projects.json
    2. Creates the Obsidian folder structure via ObsidianWriter
    3. Creates the project node in Neo4j via GraphManager
    """

    def __init__(self, graph_manager, obsidian_writer) -> None:
        self.graph_manager = graph_manager
        self.obsidian_writer = obsidian_writer

    def load_projects(self) -> Dict[str, Any]:
        """Load the projects configuration from disk.

        Returns:
            A dictionary mapping project names to their config.
        """
        if not os.path.exists(PROJECTS_CONFIG_PATH):
            return {}

        try:
            with open(PROJECTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load projects config: %s", exc)
            return {}

    def save_projects(self, projects: Dict[str, Any]) -> None:
        """Save the projects configuration to disk.

        Args:
            projects: The projects dictionary to save.
        """
        try:
            os.makedirs(os.path.dirname(PROJECTS_CONFIG_PATH), exist_ok=True)
            with open(PROJECTS_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=2)
            logger.info("Saved projects config with %d projects", len(projects))
        except OSError as exc:
            logger.error("Failed to save projects config: %s", exc)

    def create_project(
        self,
        name: str,
        path: Optional[str] = None,
        tags: Optional[list] = None,
        keywords: Optional[list] = None,
        repos: Optional[list] = None,
    ) -> None:
        """Create a new project across all systems.

        Args:
            name: The project name.
            path: Optional filesystem path for the project.
            tags: Optional list of tags.
            keywords: Optional list of keywords for matching.
            repos: Optional list of associated repo names.
        """
        logger.info("Creating new project: %s", name)

        # Update config/projects.json
        projects = self.load_projects()
        if name not in projects:
            obsidian_path = str(
                Path(self.obsidian_writer.project_vault_path) / name
            )
            projects[name] = {
                "path": path or obsidian_path,
                "status": "active",
                "tags": tags or [],
                "keywords": keywords or [],
                "repos": repos or [],
                "last_activity": datetime.utcnow().isoformat(),
            }
            self.save_projects(projects)

        # Create Obsidian folder structure
        self.obsidian_writer.ensure_project_folder(name)

        # Create initial README.md if it doesn't exist
        existing_readme = self.obsidian_writer.get_readme(name)
        if not existing_readme:
            initial_readme = f"# {name.replace('-', ' ').title()}\n\n"
            self.obsidian_writer.update_readme(name, initial_readme)

        # Create Neo4j project node
        self.graph_manager.create_or_update_project(
            name=name,
            path=path,
            status="active",
        )

        logger.info("Project '%s' created successfully", name)

    def update_project_activity(self, name: str) -> None:
        """Update the last_activity timestamp for a project.

        Args:
            name: The project name to update.
        """
        projects = self.load_projects()
        if name in projects:
            projects[name]["last_activity"] = datetime.utcnow().isoformat()
            self.save_projects(projects)

        self.graph_manager.update_project_activity(
            project_name=name,
            timestamp=datetime.utcnow().isoformat(),
        )
