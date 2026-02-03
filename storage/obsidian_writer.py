"""
Obsidian vault writer for PAIS.
Handles writing activity logs, README updates, and tweet drafts to Obsidian vaults.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ObsidianWriter:
    """Writes activity data to Obsidian vaults in Markdown format."""

    def __init__(self, project_vault: str, personal_vault: str):
        """
        Initialize the Obsidian writer with vault paths.

        Args:
            project_vault: Path to the project vault directory
            personal_vault: Path to the personal vault directory
        """
        self.project_vault = Path(project_vault)
        self.personal_vault = Path(personal_vault)
        self._ensure_vaults_exist()

    def _ensure_vaults_exist(self) -> None:
        """Create vault directories if they don't exist."""
        self.project_vault.mkdir(parents=True, exist_ok=True)
        self.personal_vault.mkdir(parents=True, exist_ok=True)
        logger.info(f"ObsidianWriter initialized with vaults: {self.project_vault}, {self.personal_vault}")

    def _to_kebab_case(self, name: str) -> str:
        """Convert a project name to kebab-case for folder naming."""
        # Replace spaces and underscores with hyphens
        name = name.replace(" ", "-").replace("_", "-")
        # Remove any non-alphanumeric characters except hyphens
        name = re.sub(r"[^a-zA-Z0-9-]", "", name)
        # Convert to lowercase
        return name.lower()

    def _format_frontmatter(self, data: Dict[str, Any]) -> str:
        """Format a dictionary as YAML frontmatter."""
        lines = ["---"]
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            elif isinstance(value, bool):
                lines.append(f"{key}: {str(value).lower()}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: \"{value}\"")
        lines.append("---")
        return "\n".join(lines)

    def ensure_project_folder(self, project_name: str) -> Path:
        """
        Ensure a project folder exists in the project vault.
        Creates folder structure with kebab-case naming.

        Args:
            project_name: Name of the project

        Returns:
            Path to the project folder
        """
        folder_name = self._to_kebab_case(project_name)
        project_folder = self.project_vault / folder_name
        project_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured project folder exists: {project_folder}")
        return project_folder

    def write_activity_log(
        self,
        project_name: str,
        activities: List[Dict[str, Any]],
    ) -> Path:
        """
        Generate/overwrite activity-log.md in the project folder.

        Args:
            project_name: Name of the project
            activities: List of activity dictionaries with date, description, technologies

        Returns:
            Path to the created file
        """
        project_folder = self.ensure_project_folder(project_name)
        log_file = project_folder / "activity-log.md"

        # Build the markdown content
        lines = [
            self._format_frontmatter({
                "project": project_name,
                "created": datetime.now().isoformat(),
                "type": "activity-log",
            }),
            "",
            f"# Activity Log: {project_name}",
            "",
        ]

        # Group activities by date
        activities_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for activity in activities:
            date = activity.get("date", activity.get("timestamp", "")[:10])
            if date:
                if date not in activities_by_date:
                    activities_by_date[date] = []
                activities_by_date[date].append(activity)

        # Sort dates in descending order
        sorted_dates = sorted(activities_by_date.keys(), reverse=True)

        for date in sorted_dates:
            lines.append(f"## {date}")
            lines.append("")

            for activity in activities_by_date[date]:
                description = activity.get("description", "No description")
                activity_type = activity.get("type", activity.get("activity_type", "activity"))
                technologies = activity.get("technologies", activity.get("tech", []))

                lines.append(f"- **[{activity_type}]** {description}")

                if technologies:
                    tech_str = ", ".join(technologies)
                    lines.append(f"  - Technologies: {tech_str}")

                lines.append("")

        # Write the file
        content = "\n".join(lines)
        log_file.write_text(content, encoding="utf-8")
        logger.info(f"Wrote activity log to {log_file} ({len(activities)} activities)")

        return log_file

    def write_personal_activity_log(
        self,
        activities: List[Dict[str, Any]],
    ) -> Path:
        """
        Write personal activities to the personal vault.

        Args:
            activities: List of activity dictionaries

        Returns:
            Path to the created file
        """
        log_file = self.personal_vault / "personal-activity-log.md"

        lines = [
            self._format_frontmatter({
                "type": "personal-activity-log",
                "updated": datetime.now().isoformat(),
            }),
            "",
            "# Personal Activity Log",
            "",
            "A record of non-project activities and learning.",
            "",
        ]

        # Group by date
        activities_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for activity in activities:
            date = activity.get("date", activity.get("timestamp", "")[:10])
            if date:
                if date not in activities_by_date:
                    activities_by_date[date] = []
                activities_by_date[date].append(activity)

        sorted_dates = sorted(activities_by_date.keys(), reverse=True)

        for date in sorted_dates:
            lines.append(f"## {date}")
            lines.append("")

            for activity in activities_by_date[date]:
                description = activity.get("description", "No description")
                activity_type = activity.get("type", activity.get("activity_type", "activity"))
                lines.append(f"- **[{activity_type}]** {description}")
                lines.append("")

        content = "\n".join(lines)
        log_file.write_text(content, encoding="utf-8")
        logger.info(f"Wrote personal activity log to {log_file}")

        return log_file

    def update_project_readme(
        self,
        project_name: str,
        weekly_summary: str,
    ) -> Path:
        """
        Prepend a weekly section to the project's README.md.

        Args:
            project_name: Name of the project
            weekly_summary: Markdown content for the weekly summary

        Returns:
            Path to the README file
        """
        project_folder = self.ensure_project_folder(project_name)
        readme_file = project_folder / "README.md"

        # Create or read existing README
        if readme_file.exists():
            existing_content = readme_file.read_text(encoding="utf-8")
        else:
            # Create new README with frontmatter
            existing_content = self._format_frontmatter({
                "project": project_name,
                "created": datetime.now().isoformat(),
                "type": "readme",
            }) + f"\n\n# {project_name}\n\n"

        # Generate the weekly section header
        week_header = f"## Week of {datetime.now().strftime('%b %d, %Y')}"
        
        # Check if this week's section already exists
        if week_header in existing_content:
            # Replace existing week section
            lines = existing_content.split("\n")
            new_lines = []
            skip_until_next_week = False
            
            for line in lines:
                if line.startswith("## Week of"):
                    if week_header in line:
                        # This is the current week, start replacement
                        new_lines.append(week_header)
                        new_lines.append("")
                        new_lines.append(weekly_summary)
                        skip_until_next_week = True
                    elif skip_until_next_week:
                        # Found next week section, stop skipping
                        new_lines.append(line)
                        skip_until_next_week = False
                    else:
                        new_lines.append(line)
                elif skip_until_next_week:
                    # Skip lines within the current week section
                    continue
                else:
                    new_lines.append(line)
            
            existing_content = "\n".join(new_lines)
        else:
            # Prepend the new weekly section
            lines = existing_content.split("\n")
            
            # Find where to insert (after the main heading and description)
            insert_index = 0
            for i, line in enumerate(lines):
                if line.startswith("# ") and i > 0:
                    insert_index = i + 1
                    break
            
            # Insert the weekly section
            weekly_section = [
                "",
                week_header,
                "",
                weekly_summary,
            ]
            lines = lines[:insert_index] + weekly_section + lines[insert_index:]
            existing_content = "\n".join(lines)

        readme_file.write_text(existing_content, encoding="utf-8")
        logger.info(f"Updated README for {project_name} with weekly summary")

        return readme_file

    def write_tweet_drafts(
        self,
        tweets: List[Dict[str, Any]],
    ) -> Path:
        """
        Write tweet drafts to tweets/drafts.md in the personal vault.

        Args:
            tweets: List of tweet draft dictionaries with content, project_name, etc.

        Returns:
            Path to the drafts file
        """
        # Ensure tweets directory exists
        tweets_dir = self.personal_vault / "tweets"
        tweets_dir.mkdir(parents=True, exist_ok=True)

        drafts_file = tweets_dir / "drafts.md"

        lines = [
            self._format_frontmatter({
                "type": "tweet-drafts",
                "updated": datetime.now().isoformat(),
            }),
            "",
            "# Tweet Drafts",
            "",
            "Drafts for social media posts generated from activities.",
            "",
        ]

        # Group tweets by date
        tweets_by_date: Dict[str, List[Dict[str, Any]]] = {}
        for tweet in tweets:
            date = tweet.get("date", tweet.get("timestamp", "")[:10])
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            if date not in tweets_by_date:
                tweets_by_date[date] = []
            tweets_by_date[date].append(tweet)

        sorted_dates = sorted(tweets_by_date.keys(), reverse=True)

        for date in sorted_dates:
            lines.append(f"## {date}")
            lines.append("")

            for tweet in tweets_by_date[date]:
                content = tweet.get("content", tweet.get("tweet", "No content"))
                project = tweet.get("project_name", tweet.get("project", "unknown"))
                posted = tweet.get("posted", False)

                lines.append(f"### Draft for {project}")
                lines.append("")
                lines.append(f"```")
                lines.append(content)
                lines.append(f"```")
                lines.append("")
                lines.append(f"- Status: {'Posted' if posted else 'Draft'}")
                
                if posted and tweet.get("posted_at"):
                    lines.append(f"- Posted at: {tweet.get('posted_at')}")
                
                lines.append("")

        content = "\n".join(lines)
        drafts_file.write_text(content, encoding="utf-8")
        logger.info(f"Wrote {len(tweets)} tweet drafts to {drafts_file}")

        return drafts_file
