"""
Obsidian vault writer for PAIS.
Handles writing activity logs, README updates, and tweet drafts to Obsidian vaults.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from storage.database import Entity

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

    def _format_activity_with_links(self, description: str, entity_map: Dict[str, Entity]) -> str:
        """
        Replace entity names in description with wiki-links.

        Args:
            description: The activity description
            entity_map: Dictionary mapping lowercase entity names to Entity objects

        Returns:
            Description with entity names replaced by wiki-links
        """
        if not entity_map:
            return description

        # Sort entities by name length (descending) to avoid partial matches
        sorted_entities = sorted(entity_map.items(), key=lambda x: len(x[0]), reverse=True)
        result = description

        for entity_name_lower, entity in sorted_entities:
            # Create wiki-link format
            if entity.display_name and entity.display_name != entity.name:
                wiki_link = f"[[{entity.name}|{entity.display_name}]]"
            else:
                wiki_link = f"[[{entity.name}]]"

            # Use word boundary regex for whole word matching
            # Escape special regex characters in entity name
            escaped_name = re.escape(entity.name)
            pattern = rf'\b{escaped_name}\b'
            result = re.sub(pattern, wiki_link, result, flags=re.IGNORECASE)

        return result

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
        entities: Optional[List[Entity]] = None,
    ) -> Path:
        """
        Generate/overwrite activity-log.md in the project folder.

        Args:
            project_name: Name of the project
            activities: List of activity dictionaries with date, description, technologies
            entities: Optional list of entities for generating wiki-links and tags

        Returns:
            Path to the created file
        """
        project_folder = self.ensure_project_folder(project_name)
        log_file = project_folder / "activity-log.md"

        # Build entity lookup map
        entity_map: Dict[str, Entity] = {}
        tags: List[str] = []
        if entities:
            for entity in entities:
                entity_map[entity.name.lower()] = entity
                if entity.display_name and entity.display_name.lower() != entity.name.lower():
                    entity_map[entity.display_name.lower()] = entity
                # Generate tags from entity types
                if entity.entity_type in ("technology", "concept"):
                    tag = entity.name.lower().replace(" ", "-").replace("_", "-")
                    if tag not in tags:
                        tags.append(tag)

        # Build the markdown content
        frontmatter_data: Dict[str, Any] = {
            "project": project_name,
            "created": datetime.now().isoformat(),
            "type": "activity-log",
        }
        if tags:
            frontmatter_data["tags"] = tags[:20]  # Limit to 20 tags

        lines = [
            self._format_frontmatter(frontmatter_data),
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

                # Format description with wiki-links if entities provided
                if entity_map:
                    description = self._format_activity_with_links(description, entity_map)

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
        entities: Optional[List[Entity]] = None,
    ) -> Path:
        """
        Prepend a weekly section to the project's README.md.

        Args:
            project_name: Name of the project
            weekly_summary: Markdown content for the weekly summary
            entities: Optional list of entities for adding Technologies and Concepts sections

        Returns:
            Path to the README file
        """
        project_folder = self.ensure_project_folder(project_name)
        readme_file = project_folder / "README.md"

        # Build entity lookup map
        entity_map: Dict[str, Entity] = {}
        technologies: List[Entity] = []
        concepts: List[Entity] = []

        if entities:
            for entity in entities:
                entity_map[entity.name.lower()] = entity
                if entity.entity_type == "technology":
                    technologies.append(entity)
                elif entity.entity_type == "concept":
                    concepts.append(entity)

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
        
        # Build weekly summary with entity sections
        weekly_content = weekly_summary

        # Add Technologies Used section
        if technologies:
            tech_links = []
            for tech in technologies:
                if tech.display_name and tech.display_name != tech.name:
                    tech_links.append(f"[[{tech.name}|{tech.display_name}]]")
                else:
                    tech_links.append(f"[[{tech.name}]]")
            weekly_content += f"\n\n**Technologies Used:** {', '.join(tech_links)}"

        # Add Related Concepts section
        if concepts:
            concept_links = []
            # Limit to top 10 concepts
            for concept in concepts[:10]:
                if concept.display_name and concept.display_name != concept.name:
                    concept_links.append(f"[[{concept.name}|{concept.display_name}]]")
                else:
                    concept_links.append(f"[[{concept.name}]]")
            weekly_content += f"\n\n**Related Concepts:** {', '.join(concept_links)}"

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
                        new_lines.append(weekly_content)
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
                weekly_content,
            ]
            lines = lines[:insert_index] + weekly_section + lines[insert_index:]
            existing_content = "\n".join(lines)

        readme_file.write_text(existing_content, encoding="utf-8")
        logger.info(f"Updated README for {project_name} with weekly summary")

        return readme_file

    def write_entity_note(
        self,
        entity: Entity,
        related_entities: Optional[List[Entity]] = None,
        projects: Optional[List[str]] = None,
    ) -> Path:
        """
        Create an individual note file for an entity.

        Args:
            entity: The entity to create a note for
            related_entities: Optional list of related entities to link
            projects: Optional list of project names where this entity is used

        Returns:
            Path to the created note file
        """
        # Only create notes for technology and concept types
        if entity.entity_type not in ("technology", "concept"):
            logger.debug(f"Skipping entity note for {entity.entity_type}: {entity.name}")
            return self.personal_vault / f"entities/{entity.name}.md"

        # Create entities directory
        entities_dir = self.personal_vault / "entities"
        entities_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = self._to_kebab_case(entity.name)
        note_file = entities_dir / f"{safe_name}.md"

        # Build tags
        tags = [entity.entity_type]
        if entity.metadata and "category" in entity.metadata:
            tags.append(entity.metadata["category"])

        # Build frontmatter
        frontmatter_data: Dict[str, Any] = {
            "type": "entity",
            "entity_type": entity.entity_type,
            "entity_name": entity.name,
            "created": datetime.now().isoformat(),
            "tags": tags,
        }
        if entity.first_seen:
            frontmatter_data["first_seen"] = entity.first_seen
        if entity.last_seen:
            frontmatter_data["last_seen"] = entity.last_seen
        if entity.mention_count > 0:
            frontmatter_data["mention_count"] = entity.mention_count

        # Build content
        lines = [
            self._format_frontmatter(frontmatter_data),
            "",
        ]

        # Title with display name if different
        if entity.display_name and entity.display_name != entity.name:
            lines.append(f"# {entity.display_name}")
            lines.append(f"\n**Canonical Name:** {entity.name}")
        else:
            lines.append(f"# {entity.name}")

        lines.append("")

        # Description section
        if entity.metadata and "description" in entity.metadata:
            lines.append("## Description")
            lines.append("")
            lines.append(entity.metadata["description"])
            lines.append("")

        # Metadata section
        if entity.metadata and any(k != "description" for k in entity.metadata.keys()):
            lines.append("## Metadata")
            lines.append("")
            for key, value in entity.metadata.items():
                if key != "description":
                    if isinstance(value, list):
                        lines.append(f"- **{key}:** {', '.join(str(v) for v in value)}")
                    else:
                        lines.append(f"- **{key}:** {value}")
            lines.append("")

        # Projects section
        if projects:
            lines.append("## Used In Projects")
            lines.append("")
            for project in projects:
                project_folder = self._to_kebab_case(project)
                lines.append(f"- [[{project_folder}/README|{project}]]")
            lines.append("")

        # Related Entities section
        if related_entities:
            lines.append("## Related")
            lines.append("")
            for related in related_entities:
                if related.entity_type in ("technology", "concept"):
                    related_safe_name = self._to_kebab_case(related.name)
                    if related.display_name and related.display_name != related.name:
                        lines.append(f"- [[entities/{related_safe_name}|{related.display_name}]] ({related.entity_type})")
                    else:
                        lines.append(f"- [[entities/{related_safe_name}|{related.name}]] ({related.entity_type})")
            lines.append("")

        # Footer with timestamps
        lines.append("---")
        lines.append("")
        lines.append(f"*Entity note generated on {datetime.now().strftime('%Y-%m-%d')}*")

        # Write the file
        content = "\n".join(lines)
        note_file.write_text(content, encoding="utf-8")
        logger.info(f"Wrote entity note to {note_file}")

        return note_file

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
