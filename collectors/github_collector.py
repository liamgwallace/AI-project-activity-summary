"""GitHub activity collector.

Fetches recent commits and pull request events from the GitHub REST API
for a configured user and stores them as activity events.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from collectors.base_collector import BaseCollector
from config.settings import DATA_DIR, GITHUB_TOKEN, GITHUB_USERNAME
from storage.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)

LAST_COLLECTED_FILE = os.path.join(DATA_DIR, "github_last_collected.txt")


class GitHubCollector(BaseCollector):
    """Collector that gathers activity from the GitHub REST API.

    Fetches public events for the configured GITHUB_USERNAME, filtering
    for PushEvent (commits) and PullRequestEvent (pull requests).
    Authentication is performed via a personal access token stored in
    GITHUB_TOKEN.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        super().__init__(sqlite_manager)
        self.username: str = GITHUB_USERNAME
        self.token: Optional[str] = GITHUB_TOKEN
        self.api_base: str = "https://api.github.com"
        self._last_collected_path: str = LAST_COLLECTED_FILE

    @property
    def source(self) -> str:
        return "github"

    # ------------------------------------------------------------------
    # Timestamp tracking
    # ------------------------------------------------------------------

    def _read_last_collected(self) -> Optional[datetime]:
        """Read the last collection timestamp from disk.

        Returns:
            A timezone-aware datetime, or None if no previous run recorded.
        """
        try:
            path = Path(self._last_collected_path)
            if path.exists():
                raw = path.read_text().strip()
                if raw:
                    return datetime.fromisoformat(raw)
        except Exception as exc:
            self.logger.warning("Could not read last collected timestamp: %s", exc)
        return None

    def _write_last_collected(self, ts: datetime) -> None:
        """Persist the latest collection timestamp to disk.

        Args:
            ts: The datetime to record.
        """
        try:
            path = Path(self._last_collected_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(ts.isoformat())
        except Exception as exc:
            self.logger.warning("Could not write last collected timestamp: %s", exc)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for GitHub API requests."""
        headers: Dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch the user's public events from the GitHub Events API.

        Returns:
            A list of raw event dictionaries from the API.
        """
        url = f"{self.api_base}/users/{self.username}/events"
        all_events: List[Dict[str, Any]] = []
        page = 1
        per_page = 100

        while page <= 3:  # GitHub caps at 10 pages / 300 events
            self.logger.debug("Fetching GitHub events page %d", page)
            try:
                response = requests.get(
                    url,
                    headers=self._build_headers(),
                    params={"per_page": per_page, "page": page},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                self.logger.error("GitHub API request failed: %s", exc)
                break

            data = response.json()
            if not data:
                break

            all_events.extend(data)
            page += 1

        return all_events

    # ------------------------------------------------------------------
    # Event parsing
    # ------------------------------------------------------------------

    def _parse_push_event(
        self, event: Dict[str, Any], created_at: str
    ) -> List[Dict[str, Any]]:
        """Extract individual commit events from a PushEvent payload.

        Args:
            event: The raw GitHub event dictionary.
            created_at: ISO-8601 timestamp string of the event.

        Returns:
            A list of normalised commit event dictionaries.
        """
        results: List[Dict[str, Any]] = []
        repo_name = event.get("repo", {}).get("name", "unknown")
        payload = event.get("payload", {})
        commits = payload.get("commits", [])

        for commit in commits:
            sha = commit.get("sha", "")
            message = commit.get("message", "")
            url = f"https://github.com/{repo_name}/commit/{sha}"
            results.append(
                {
                    "source": self.source,
                    "event_type": "commit",
                    "timestamp": created_at,
                    "data": {
                        "message": message,
                        "repo": repo_name,
                        "sha": sha,
                        "url": url,
                    },
                }
            )
        return results

    def _parse_pull_request_event(
        self, event: Dict[str, Any], created_at: str
    ) -> List[Dict[str, Any]]:
        """Extract a pull request event from a PullRequestEvent payload.

        Args:
            event: The raw GitHub event dictionary.
            created_at: ISO-8601 timestamp string of the event.

        Returns:
            A single-element list with the normalised PR event dictionary.
        """
        repo_name = event.get("repo", {}).get("name", "unknown")
        payload = event.get("payload", {})
        pr = payload.get("pull_request", {})
        action = payload.get("action", "unknown")

        return [
            {
                "source": self.source,
                "event_type": "pull_request",
                "timestamp": created_at,
                "data": {
                    "title": pr.get("title", ""),
                    "body": pr.get("body", ""),
                    "repo": repo_name,
                    "url": pr.get("html_url", ""),
                    "action": action,
                },
            }
        ]

    # ------------------------------------------------------------------
    # Main collect
    # ------------------------------------------------------------------

    def collect(self) -> List[Dict[str, Any]]:
        """Collect recent GitHub commit and pull request events.

        Returns:
            A list of normalised event dictionaries ready for storage.
        """
        if not self.username:
            self.logger.error("GITHUB_USERNAME is not configured. Skipping collection.")
            return []

        last_collected = self._read_last_collected()
        raw_events = self._fetch_events()
        self.logger.debug("Fetched %d raw GitHub events.", len(raw_events))

        parsed_events: List[Dict[str, Any]] = []
        latest_ts: Optional[datetime] = None

        for event in raw_events:
            event_type = event.get("type", "")
            created_at = event.get("created_at", "")

            # Parse event timestamp and skip if already collected
            try:
                event_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            if last_collected and event_dt <= last_collected:
                continue

            if latest_ts is None or event_dt > latest_ts:
                latest_ts = event_dt

            if event_type == "PushEvent":
                parsed_events.extend(self._parse_push_event(event, created_at))
            elif event_type == "PullRequestEvent":
                parsed_events.extend(
                    self._parse_pull_request_event(event, created_at)
                )

        # Update last-collected marker
        if latest_ts is not None:
            self._write_last_collected(latest_ts)

        return parsed_events
