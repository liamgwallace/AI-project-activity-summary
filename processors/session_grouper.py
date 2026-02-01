"""
Session grouper for the Personal Activity Intelligence System.

Groups raw events into logical sessions based on time proximity.
Events occurring within a configurable gap (default 60 minutes) of each
other are grouped into the same session.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from config import settings
from utils.helpers import parse_datetime

logger = logging.getLogger(__name__)


class SessionGrouper:
    """Groups activity events into time-based sessions.

    A session is defined as a contiguous sequence of events where no two
    consecutive events are more than `gap_minutes` apart. Once events are
    grouped, session records are created in the sessions table and each
    event is assigned a session_id.

    Attributes:
        sqlite_manager: The SQLite database manager instance.
        gap_minutes: Maximum gap in minutes between consecutive events
            within the same session.
    """

    def __init__(
        self,
        sqlite_manager,
        gap_minutes: Optional[int] = None,
    ) -> None:
        """Initialize the SessionGrouper.

        Args:
            sqlite_manager: SQLite database manager providing query and
                execute methods for the events and sessions tables.
            gap_minutes: Maximum number of minutes between consecutive
                events to consider them part of the same session.
                Defaults to config.settings.SESSION_GAP_MINUTES.
        """
        self.sqlite_manager = sqlite_manager
        self.gap_minutes = gap_minutes or getattr(
            settings, "SESSION_GAP_MINUTES", 60
        )
        logger.info(
            "SessionGrouper initialized with gap_minutes=%d", self.gap_minutes
        )

    def group_events(self) -> list[int]:
        """Fetch unprocessed events and group them into sessions.

        Queries all events where processed=0 and session_id IS NULL,
        orders them by timestamp, and groups consecutive events into
        sessions based on the time gap threshold.

        For each session, a record is created in the sessions table with
        a unique session_id, start_time, end_time, and event_count.
        Each event in the session is updated with the corresponding
        session_id.

        Returns:
            A list of newly created session IDs (integers).
        """
        logger.info("Starting event grouping into sessions")

        # Fetch unprocessed events ordered by timestamp
        events = self.sqlite_manager.query(
            """
            SELECT id, timestamp, source, event_type, data
            FROM events
            WHERE processed = 0 AND session_id IS NULL
            ORDER BY timestamp ASC
            """,
        )

        if not events:
            logger.info("No unprocessed events found for grouping")
            return []

        logger.info("Found %d unprocessed events to group", len(events))

        # Group events into sessions based on time gaps
        sessions = self._group_by_gap(events)

        logger.info(
            "Grouped %d events into %d sessions", len(events), len(sessions)
        )

        # Create session records and assign session IDs to events
        new_session_ids: list[int] = []

        for session_events in sessions:
            session_id = self._create_session(session_events)
            if session_id:
                new_session_ids.append(session_id)

        logger.info("Created %d new sessions", len(new_session_ids))
        return new_session_ids

    def _group_by_gap(self, events: list[dict]) -> list[list[dict]]:
        """Group a sorted list of events into sessions by time gap.

        Events are assumed to be sorted by timestamp ascending. A new
        session is started whenever the gap between consecutive events
        exceeds gap_minutes.

        Args:
            events: List of event dicts, each containing at least an
                'id' and 'timestamp' field. Must be sorted by timestamp.

        Returns:
            A list of lists, where each inner list is a group of events
            forming a session.
        """
        if not events:
            return []

        gap_delta = timedelta(minutes=self.gap_minutes)
        sessions: list[list[dict]] = []
        current_session: list[dict] = [events[0]]

        for i in range(1, len(events)):
            current_event = events[i]
            previous_event = current_session[-1]

            current_time = self._parse_event_timestamp(current_event)
            previous_time = self._parse_event_timestamp(previous_event)

            if current_time is None or previous_time is None:
                # If we can't parse timestamps, keep in same session
                logger.warning(
                    "Could not parse timestamp for event %s or %s, "
                    "keeping in same session",
                    current_event.get("id"),
                    previous_event.get("id"),
                )
                current_session.append(current_event)
                continue

            if (current_time - previous_time) > gap_delta:
                # Gap exceeded - start a new session
                sessions.append(current_session)
                current_session = [current_event]
            else:
                current_session.append(current_event)

        # Don't forget the last session
        if current_session:
            sessions.append(current_session)

        return sessions

    def _create_session(self, session_events: list[dict]) -> Optional[int]:
        """Create a session record and assign session_id to its events.

        Args:
            session_events: List of event dicts belonging to this session.

        Returns:
            The session_id (integer) if successful, None otherwise.
        """
        if not session_events:
            return None

        first_timestamp = session_events[0].get("timestamp", "")
        last_timestamp = session_events[-1].get("timestamp", "")

        try:
            # Insert session record and get auto-generated ID
            results = self.sqlite_manager.query(
                """
                INSERT INTO sessions (
                    start_time, end_time, event_count, processed
                ) VALUES (?, ?, ?, 0)
                RETURNING id
                """,
                (
                    first_timestamp,
                    last_timestamp,
                    len(session_events),
                ),
            )
            session_id = results[0]["id"]

            # Update each event with the session_id
            event_ids = [event["id"] for event in session_events]
            placeholders = ",".join("?" for _ in event_ids)
            self.sqlite_manager.execute(
                f"""
                UPDATE events
                SET session_id = ?
                WHERE id IN ({placeholders})
                """,
                tuple([session_id] + event_ids),
            )

            logger.debug(
                "Created session %d: %s to %s (%d events)",
                session_id,
                first_timestamp,
                last_timestamp,
                len(session_events),
            )

            return session_id

        except Exception as e:
            logger.error(
                "Failed to create session for %d events: %s",
                len(session_events),
                str(e),
            )
            return None

    @staticmethod
    def _parse_event_timestamp(event: dict) -> Optional[datetime]:
        """Parse the timestamp from an event dict.

        Args:
            event: An event dict with a 'timestamp' key.

        Returns:
            A datetime object, or None if parsing fails.
        """
        timestamp_str = event.get("timestamp", "")
        return parse_datetime(timestamp_str)
