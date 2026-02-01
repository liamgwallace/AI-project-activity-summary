"""Activity log generator for the Personal Activity Intelligence System.

Generates human-readable activity-log.md files from database events,
grouped by date and session, for output to Obsidian vaults.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Generates activity-log.md content from stored events.

    Produces a markdown document showing the last N days of activity,
    grouped by date and session, with human-readable event descriptions.
    """

    def __init__(self, sqlite_manager, obsidian_writer) -> None:
        self.sqlite_manager = sqlite_manager
        self.obsidian_writer = obsidian_writer
        self.log_days = settings.activity_log_days

    def generate_project_log(self, project_name: str) -> str:
        """Generate activity-log.md content for a specific project.

        Args:
            project_name: The project to generate the log for.

        Returns:
            Markdown string of the activity log.
        """
        cutoff = (datetime.utcnow() - timedelta(days=self.log_days)).isoformat()

        events_by_date = self.sqlite_manager.get_events_for_activity_log(
            days=self.log_days
        )

        lines = ["# Activity Log\n"]

        for date_str in sorted(events_by_date.keys(), reverse=True):
            events = events_by_date[date_str]
            lines.append(f"\n## {date_str}")

            # Group events by session
            sessions = self._group_events_by_session(events)

            for session_events in sessions:
                if not session_events:
                    continue

                start = session_events[0].get("timestamp", "")[:16].replace("T", " ")
                end = session_events[-1].get("timestamp", "")[:16].split("T")[-1] if len(session_events) > 1 else ""

                session_header = f"**Session {start}"
                if end:
                    session_header += f" - {end}"
                session_header += "**"
                lines.append(session_header)

                for event in session_events:
                    line = self._format_event_line(event)
                    lines.append(line)

                lines.append("")

        content = "\n".join(lines) + "\n"

        # Write to Obsidian
        self.obsidian_writer.write_activity_log(project_name, content)
        logger.info("Generated activity log for project: %s", project_name)

        return content

    def generate_personal_log(self) -> str:
        """Generate the personal (non-project) activity log.

        Returns:
            Markdown string of the personal activity log.
        """
        events_by_date = self.sqlite_manager.get_events_for_activity_log(
            days=self.log_days
        )

        lines = ["# Activity Log\n"]

        for date_str in sorted(events_by_date.keys(), reverse=True):
            events = events_by_date[date_str]
            lines.append(f"\n## {date_str}")

            sessions = self._group_events_by_session(events)

            for session_events in sessions:
                if not session_events:
                    continue

                start = session_events[0].get("timestamp", "")[:16].replace("T", " ")
                end = session_events[-1].get("timestamp", "")[:16].split("T")[-1] if len(session_events) > 1 else ""

                session_header = f"**Session {start}"
                if end:
                    session_header += f" - {end}"
                session_header += "**"
                lines.append(session_header)

                for event in session_events:
                    line = self._format_event_line(event)
                    lines.append(line)

                lines.append("")

        content = "\n".join(lines) + "\n"

        self.obsidian_writer.write_personal_activity_log(content)
        logger.info("Generated personal activity log")

        return content

    def _group_events_by_session(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events by session_id, preserving order."""
        sessions: Dict[Optional[int], List[Dict[str, Any]]] = {}
        order: List[Optional[int]] = []

        for event in events:
            sid = event.get("session_id")
            if sid not in sessions:
                sessions[sid] = []
                order.append(sid)
            sessions[sid].append(event)

        return [sessions[sid] for sid in order]

    @staticmethod
    def _format_event_line(event: Dict[str, Any]) -> str:
        """Format a single event as a markdown line."""
        timestamp = event.get("timestamp", "")
        time_part = timestamp[11:16] if len(timestamp) >= 16 else timestamp
        source = event.get("source", "")
        event_type = event.get("event_type", "")
        data = event.get("data", {})

        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}

        if event_type == "commit":
            message = data.get("message", "")
            repo = data.get("repo", "")
            return f"- {time_part} - Commit: \"{message}\" ({repo})"
        elif event_type == "page_view":
            title = data.get("title", "")
            url = data.get("url", "")
            return f"- {time_part} - Viewed: [{title}]({url})"
        elif event_type == "file_edit":
            path = data.get("path", "")
            filename = path.split("/")[-1] if path else ""
            return f"- {time_part} - Modified: `{filename}`"
        elif event_type == "email":
            subject = data.get("subject", "")
            return f"- {time_part} - Email: {subject}"
        elif event_type == "calendar_event":
            title = data.get("title", "")
            return f"- {time_part} - Calendar: \"{title}\""
        else:
            return f"- {time_part} - ({source}/{event_type})"
