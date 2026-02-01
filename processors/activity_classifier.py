"""Activity classifier for the Personal Activity Intelligence System.

Determines which project an event or session belongs to based on
configured project roots, repository names, keywords, and tags.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from config.settings import CONFIG_DIR

logger = logging.getLogger(__name__)

PROJECTS_CONFIG_PATH = os.path.join(CONFIG_DIR, "projects.json")


class ActivityClassifier:
    """Classifies activity events to projects using heuristics.

    Uses project configuration (paths, repos, keywords, tags) to match
    events to projects before AI processing. This provides a first-pass
    classification that the AI can refine.
    """

    def __init__(self) -> None:
        self._projects = self._load_projects()

    def _load_projects(self) -> Dict[str, Any]:
        """Load projects configuration."""
        if not os.path.exists(PROJECTS_CONFIG_PATH):
            return {}
        try:
            with open(PROJECTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load projects config: %s", exc)
            return {}

    def reload(self) -> None:
        """Reload the projects configuration from disk."""
        self._projects = self._load_projects()

    def classify_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Classify a single event to a project.

        Args:
            event: An event dictionary with source, event_type, and data fields.

        Returns:
            The project name if a match is found, None otherwise.
        """
        source = event.get("source", "")
        data = event.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}

        # Match by repository name (GitHub events)
        if source == "github":
            repo = data.get("repo", "")
            match = self._match_by_repo(repo)
            if match:
                return match

        # Match by file path (filesystem events)
        if source == "filesystem":
            path = data.get("path", "")
            match = self._match_by_path(path)
            if match:
                return match

        # Match by keywords in event data
        match = self._match_by_keywords(data)
        if match:
            return match

        return None

    def classify_events(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classify a list of events by project.

        Args:
            events: List of event dictionaries.

        Returns:
            A dict mapping project names (or 'unclassified') to lists of events.
        """
        classified: Dict[str, List[Dict[str, Any]]] = {}

        for event in events:
            project = self.classify_event(event) or "unclassified"
            classified.setdefault(project, []).append(event)

        return classified

    def _match_by_repo(self, repo: str) -> Optional[str]:
        """Match by repository name."""
        if not repo:
            return None

        for project_name, config in self._projects.items():
            repos = config.get("repos", [])
            for project_repo in repos:
                if repo.endswith(project_repo) or project_repo in repo:
                    return project_name
        return None

    def _match_by_path(self, path: str) -> Optional[str]:
        """Match by filesystem path."""
        if not path:
            return None

        best_match = None
        best_length = 0

        for project_name, config in self._projects.items():
            project_path = config.get("path", "")
            if project_path and path.startswith(project_path):
                if len(project_path) > best_length:
                    best_match = project_name
                    best_length = len(project_path)

        return best_match

    def _match_by_keywords(self, data: Dict[str, Any]) -> Optional[str]:
        """Match by keywords in event data."""
        data_text = json.dumps(data).lower()

        best_match = None
        best_score = 0

        for project_name, config in self._projects.items():
            keywords = config.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in data_text)
            if score > best_score:
                best_score = score
                best_match = project_name

        return best_match if best_score > 0 else None
