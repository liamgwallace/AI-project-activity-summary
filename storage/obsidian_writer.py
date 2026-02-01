"""Obsidian vault markdown file writer for the Personal Activity Intelligence System.

Generates and manages markdown files in Obsidian vaults for both per-project
activity logs and personal activity summaries.
"""

import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger("storage.obsidian")


class ObsidianWriter:
    """Writes structured markdown content to Obsidian vaults.

    Supports two vaults:
      - A **project vault** where each project gets its own folder containing
        an ``activity-log.md`` and ``README.md``.
      - A **personal vault** for cross-project personal activity logs.

    Also manages tweet draft output files under ``outputs/tweets/``.
    """

    def __init__(
        self,
        project_vault_path: Optional[str] = None,
        personal_vault_path: Optional[str] = None,
    ) -> None:
        """Initialize the Obsidian writer.

        Args:
            project_vault_path: Root path of the project Obsidian vault.
                Falls back to config.settings.OBSIDIAN_PROJECT_VAULT_PATH.
            personal_vault_path: Root path of the personal Obsidian vault.
                Falls back to config.settings.OBSIDIAN_PERSONAL_VAULT_PATH.
        """
        self.project_vault_path = Path(
            project_vault_path or settings.OBSIDIAN_PROJECT_VAULT_PATH
        )
        self.personal_vault_path = Path(
            personal_vault_path or settings.OBSIDIAN_PERSONAL_VAULT_PATH
        )
        logger.info(
            "ObsidianWriter initialized: project_vault=%s, personal_vault=%s",
            self.project_vault_path,
            self.personal_vault_path,
        )

    # ------------------------------------------------------------------
    # Folder management
    # ------------------------------------------------------------------

    def ensure_project_folder(self, project_name: str) -> Path:
        """Create the project folder inside the project vault if it does not exist.

        Args:
            project_name: Name of the project (used as folder name).

        Returns:
            The Path to the project folder.
        """
        folder = self.project_vault_path / project_name
        folder.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured project folder exists: %s", folder)
        return folder

    # ------------------------------------------------------------------
    # Activity log operations
    # ------------------------------------------------------------------

    def write_activity_log(self, project_name: str, content: str) -> Path:
        """Write (overwrite) the activity-log.md for a project.

        Args:
            project_name: Name of the project.
            content: Full markdown content for the activity log.

        Returns:
            The Path to the written file.
        """
        folder = self.ensure_project_folder(project_name)
        file_path = folder / "activity-log.md"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Wrote activity log: %s", file_path)
        return file_path

    def get_activity_log(self, project_name: str) -> str:
        """Read the current activity-log.md content for a project.

        Args:
            project_name: Name of the project.

        Returns:
            The file content as a string, or an empty string if the file
            does not exist.
        """
        file_path = self.project_vault_path / project_name / "activity-log.md"
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Read activity log: %s (%d chars)", file_path, len(content))
            return content
        logger.debug("Activity log not found: %s", file_path)
        return ""

    def write_personal_activity_log(self, content: str) -> Path:
        """Write (overwrite) the personal activity log in the personal vault.

        The file is written to ``<personal_vault>/activity-log.md``.

        Args:
            content: Full markdown content for the personal activity log.

        Returns:
            The Path to the written file.
        """
        self.personal_vault_path.mkdir(parents=True, exist_ok=True)
        file_path = self.personal_vault_path / "activity-log.md"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Wrote personal activity log: %s", file_path)
        return file_path

    # ------------------------------------------------------------------
    # README operations
    # ------------------------------------------------------------------

    def update_readme(self, project_name: str, content: str) -> Path:
        """Write (overwrite) the README.md for a project.

        Args:
            project_name: Name of the project.
            content: Full markdown content for the README.

        Returns:
            The Path to the written file.
        """
        folder = self.ensure_project_folder(project_name)
        file_path = folder / "README.md"
        file_path.write_text(content, encoding="utf-8")
        logger.info("Wrote README: %s", file_path)
        return file_path

    def get_readme(self, project_name: str) -> str:
        """Read the current README.md content for a project.

        Args:
            project_name: Name of the project.

        Returns:
            The file content as a string, or an empty string if the file
            does not exist.
        """
        file_path = self.project_vault_path / project_name / "README.md"
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Read README: %s (%d chars)", file_path, len(content))
            return content
        logger.debug("README not found: %s", file_path)
        return ""

    # ------------------------------------------------------------------
    # Tweet draft operations
    # ------------------------------------------------------------------

    def write_tweet_draft(
        self,
        filename: str = "",
        content: str = "",
        description: str = "",
        tweet_text: str = "",
        project_name: Optional[str] = None,
    ) -> Path:
        """Write a tweet draft to the outputs/tweets/ directory.

        Can be called with positional (filename, content) or with keyword
        args (description, tweet_text, project_name) for convenience.

        Returns:
            The Path to the written file.
        """
        from datetime import datetime as _dt

        tweets_dir = Path(settings.OUTPUTS_DIR) / "tweets"
        tweets_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            now = _dt.utcnow()
            filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}"
            if project_name:
                filename += f"_{project_name}"
            filename += ".md"

        if not content:
            content = (
                f"---\nproject: {project_name or 'none'}\nstatus: draft\n---\n\n"
                f"## {description}\n\n{tweet_text}\n"
            )

        file_path = tweets_dir / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info("Wrote tweet draft: %s", file_path)
        return file_path

    # ------------------------------------------------------------------
    # Adapter methods for processor compatibility
    # ------------------------------------------------------------------

    def create_project_folder(self, project_name: str) -> Path:
        """Alias for ensure_project_folder."""
        return self.ensure_project_folder(project_name)

    def read_file(self, project_name: str, filename: str) -> Optional[str]:
        """Read any file from a project folder.

        Args:
            project_name: Name of the project.
            filename: Name of the file to read.

        Returns:
            File content as string, or None if not found.
        """
        file_path = self.project_vault_path / project_name / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def write_file(self, project_name: str, filename: str, content: str) -> Path:
        """Write any file to a project folder.

        Args:
            project_name: Name of the project.
            filename: Name of the file to write.
            content: Content to write.

        Returns:
            The Path to the written file.
        """
        folder = self.ensure_project_folder(project_name)
        file_path = folder / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info("Wrote file: %s", file_path)
        return file_path

    def regenerate_activity_log(self, project_name: str) -> None:
        """Placeholder for activity log regeneration.

        The actual regeneration logic lives in generators/activity_logger.py.

        Args:
            project_name: Name of the project.
        """
        logger.debug(
            "Activity log regeneration requested for project: %s",
            project_name,
        )
