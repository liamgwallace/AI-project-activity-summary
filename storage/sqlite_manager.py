"""SQLite operations manager for the Personal Activity Intelligence System.

Provides structured storage for events, sessions, caching, and AI call logging
using SQLite with JSON support for flexible event data.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import settings

logger = logging.getLogger("storage.sqlite")


class SQLiteManager:
    """Manages all SQLite database operations for event storage, session tracking,
    summary caching, and AI usage logging.

    Uses context managers for safe connection handling and supports JSON
    serialization of flexible event data payloads.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the SQLite manager.

        Args:
            db_path: Path to the SQLite database file. Falls back to
                     config.settings.SQLITE_DB_PATH if not provided.
        """
        self.db_path = db_path or settings.SQLITE_DB_PATH
        logger.info("SQLiteManager initialized with db_path=%s", self.db_path)

    @contextmanager
    def _get_connection(self):
        """Context manager that yields a SQLite connection with row_factory set.

        Commits on successful exit, rolls back on exception, and always closes
        the connection.

        Yields:
            sqlite3.Connection: An open database connection.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _get_cursor(self):
        """Context manager that yields a cursor from a managed connection.

        Yields:
            Tuple[sqlite3.Connection, sqlite3.Cursor]: The connection and cursor.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            yield conn, cursor

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def initialize_db(self) -> None:
        """Create all required tables if they do not already exist.

        Tables created:
            - events: Raw activity events from all sources.
            - sessions: Grouped time windows of events.
            - cache: Web-page summary cache with expiry.
            - ai_logs: Audit trail for AI/LLM API calls.
        """
        logger.info("Initializing database schema")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       DATETIME NOT NULL,
                    source          TEXT NOT NULL,
                    event_type      TEXT NOT NULL,
                    data            JSON,
                    session_id      INTEGER,
                    processed       BOOLEAN DEFAULT 0,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time      DATETIME NOT NULL,
                    end_time        DATETIME NOT NULL,
                    event_count     INTEGER NOT NULL DEFAULT 0,
                    processed       BOOLEAN DEFAULT 0,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webpage_cache (
                    url             TEXT PRIMARY KEY,
                    title           TEXT,
                    summary         TEXT NOT NULL,
                    cached_at       DATETIME NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type       TEXT NOT NULL,
                    input_tokens    INTEGER,
                    output_tokens   INTEGER,
                    model_used      TEXT,
                    duration_seconds REAL,
                    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error           TEXT
                )
            """)

            # Indexes for common query patterns
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON events(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_session_id
                ON events(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_processed
                ON events(processed)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_processed
                ON sessions(processed)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_cached_at
                ON webpage_cache(cached_at)
            """)

        logger.info("Database schema initialized successfully")

    # ------------------------------------------------------------------
    # Event operations
    # ------------------------------------------------------------------

    def insert_event(
        self,
        timestamp: str,
        source: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> int:
        """Insert a new activity event into the events table.

        Args:
            timestamp: ISO-format datetime string for when the event occurred.
            source: Origin of the event (github, filesystem, chrome, gmail, calendar).
            event_type: Kind of event (commit, file_edit, page_view, email, calendar_event).
            data: Arbitrary JSON-serialisable payload with event details.

        Returns:
            The auto-generated integer id of the newly inserted event.
        """
        serialized_data = json.dumps(data)
        logger.debug(
            "Inserting event: source=%s, type=%s, timestamp=%s",
            source,
            event_type,
            timestamp,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (timestamp, source, event_type, data)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, source, event_type, serialized_data),
            )
            event_id = cursor.lastrowid

        logger.info("Inserted event id=%d", event_id)
        return event_id

    def get_unprocessed_events(self) -> List[Dict[str, Any]]:
        """Retrieve all events that have not yet been processed.

        Returns:
            A list of event dictionaries with the ``data`` field deserialised
            from JSON.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE processed = 0 ORDER BY timestamp ASC"
            )
            rows = cursor.fetchall()

        events = [self._row_to_event_dict(row) for row in rows]
        logger.debug("Retrieved %d unprocessed events", len(events))
        return events

    def get_events_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Retrieve all events belonging to a specific session.

        Args:
            session_id: The session identifier.

        Returns:
            A list of event dictionaries ordered by timestamp.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
            rows = cursor.fetchall()

        events = [self._row_to_event_dict(row) for row in rows]
        logger.debug(
            "Retrieved %d events for session_id=%d", len(events), session_id
        )
        return events

    def get_events_in_range(
        self, start_time: str, end_time: str
    ) -> List[Dict[str, Any]]:
        """Retrieve all events within a time range (inclusive).

        Args:
            start_time: ISO-format start datetime.
            end_time: ISO-format end datetime.

        Returns:
            A list of event dictionaries ordered by timestamp.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM events
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (start_time, end_time),
            )
            rows = cursor.fetchall()

        events = [self._row_to_event_dict(row) for row in rows]
        logger.debug(
            "Retrieved %d events in range %s to %s",
            len(events),
            start_time,
            end_time,
        )
        return events

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def create_session(
        self, start_time: str, end_time: str, event_count: int
    ) -> int:
        """Create a new session record.

        Args:
            start_time: ISO-format start datetime of the session.
            end_time: ISO-format end datetime of the session.
            event_count: Number of events contained in this session.

        Returns:
            The auto-generated integer id of the newly created session.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (start_time, end_time, event_count)
                VALUES (?, ?, ?)
                """,
                (start_time, end_time, event_count),
            )
            session_id = cursor.lastrowid

        logger.info("Created session id=%d (%s -> %s)", session_id, start_time, end_time)
        return session_id

    def assign_events_to_session(
        self, event_ids: List[int], session_id: int
    ) -> None:
        """Assign a batch of events to a session.

        Args:
            event_ids: List of event ids to assign.
            session_id: The target session id.
        """
        if not event_ids:
            logger.warning("assign_events_to_session called with empty event_ids")
            return

        placeholders = ",".join("?" for _ in event_ids)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE events
                SET session_id = ?
                WHERE id IN ({placeholders})
                """,
                [session_id] + list(event_ids),
            )

        logger.info(
            "Assigned %d events to session_id=%d", len(event_ids), session_id
        )

    def mark_session_processed(self, session_id: int) -> None:
        """Mark a session and all its events as processed.

        Args:
            session_id: The session to mark.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET processed = 1 WHERE id = ?",
                (session_id,),
            )
            cursor.execute(
                "UPDATE events SET processed = 1 WHERE session_id = ?",
                (session_id,),
            )

        logger.info("Marked session_id=%d as processed", session_id)

    def get_unprocessed_sessions(self) -> List[Dict[str, Any]]:
        """Retrieve all sessions that have not yet been processed.

        Returns:
            A list of session dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions WHERE processed = 0 ORDER BY start_time ASC"
            )
            rows = cursor.fetchall()

        sessions = [dict(row) for row in rows]
        logger.debug("Retrieved %d unprocessed sessions", len(sessions))
        return sessions

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get_cached_summary(self, url: str) -> Optional[str]:
        """Look up a cached web-page summary, respecting expiry.

        Args:
            url: The URL to look up.

        Returns:
            The cached summary text, or ``None`` if the entry does not exist
            or has expired.
        """
        now = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT summary FROM webpage_cache
                WHERE url = ? AND expires_at > ?
                """,
                (url, now),
            )
            row = cursor.fetchone()

        if row:
            logger.debug("Cache hit for url=%s", url)
            return row["summary"]

        logger.debug("Cache miss for url=%s", url)
        return None

    def cache_summary(
        self, url: str, summary: str, expiry_days: int = 7
    ) -> None:
        """Store or update a web-page summary in the cache.

        Args:
            url: The URL to cache.
            summary: The summary text.
            expiry_days: Number of days before the cache entry expires.
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(days=expiry_days)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO webpage_cache (url, summary, cached_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    summary = excluded.summary,
                    cached_at = excluded.cached_at,
                    expires_at = excluded.expires_at
                """,
                (url, summary, now.isoformat(), expires_at.isoformat()),
            )

        logger.info("Cached summary for url=%s (expires %s)", url, expires_at.isoformat())

    def cleanup_expired_cache(self) -> int:
        """Delete all expired cache entries.

        Returns:
            The number of rows deleted.
        """
        now = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM webpage_cache WHERE expires_at <= ?", (now,))
            deleted = cursor.rowcount

        logger.info("Cleaned up %d expired cache entries", deleted)
        return deleted

    # ------------------------------------------------------------------
    # AI logging
    # ------------------------------------------------------------------

    def log_ai_call(
        self,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
        model_used: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> int:
        """Record an AI/LLM API call for auditing and cost tracking.

        Args:
            task_type: The kind of AI task (e.g. 'summarise', 'classify').
            input_tokens: Number of prompt tokens consumed.
            output_tokens: Number of completion tokens produced.
            model_used: Identifier of the model (e.g. 'gpt-4').
            duration_seconds: Wall-clock time of the API call.
            error: Optional error message if the call failed.

        Returns:
            The auto-generated integer id of the log entry.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ai_logs
                    (task_type, input_tokens, output_tokens, model_used,
                     duration_seconds, error)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_type,
                    input_tokens,
                    output_tokens,
                    model_used,
                    duration_seconds,
                    error,
                ),
            )
            log_id = cursor.lastrowid

        logger.info(
            "Logged AI call id=%d: task=%s, model=%s, tokens=%d+%d, %.2fs%s",
            log_id,
            task_type,
            model_used,
            input_tokens,
            output_tokens,
            duration_seconds,
            f", error={error}" if error else "",
        )
        return log_id

    # ------------------------------------------------------------------
    # Activity log query
    # ------------------------------------------------------------------

    def get_events_for_activity_log(
        self, days: int = 7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve recent events grouped by date for activity-log generation.

        Args:
            days: Number of past days to include (default 7).

        Returns:
            A dict mapping ISO date strings (YYYY-MM-DD) to lists of event
            dictionaries, sorted chronologically.
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM events
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            event = self._row_to_event_dict(row)
            date_key = event["timestamp"][:10]  # YYYY-MM-DD
            grouped.setdefault(date_key, []).append(event)

        logger.debug(
            "Retrieved events for activity log: %d days, %d dates, %d total events",
            days,
            len(grouped),
            sum(len(v) for v in grouped.values()),
        )
        return grouped

    # ------------------------------------------------------------------
    # Generic query / execute
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as a list of dicts.

        Args:
            sql: The SQL query string.
            params: Query parameters.

        Returns:
            A list of dictionaries, one per row.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a write SQL statement (INSERT, UPDATE, DELETE).

        Args:
            sql: The SQL statement string.
            params: Statement parameters.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_event_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row from the events table into a plain dict,
        deserialising the JSON ``data`` column.

        Args:
            row: A sqlite3.Row object.

        Returns:
            A dictionary representation of the event.
        """
        event = dict(row)
        if event.get("data"):
            try:
                event["data"] = json.loads(event["data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Failed to decode JSON data for event id=%s", event.get("id")
                )
        return event
