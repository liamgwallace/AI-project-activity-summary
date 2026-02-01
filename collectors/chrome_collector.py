"""Chrome browser history collector.

Fetches recent browsing history via Chrome's History Sync API using OAuth2.
Falls back to reading the local Chrome History SQLite database directly when
the API approach is unavailable.

NOTE: The Chrome History Sync API has limited public availability. Google
does not expose a fully public History API in the same way as Gmail or
Calendar.  For many setups the most reliable approach is the direct SQLite
fallback (reading ``~/.config/google-chrome/Default/History`` on Linux or
the equivalent path on macOS / Windows).  The OAuth flow is kept here as a
reference implementation in case access is granted via a custom OAuth client.
"""

import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from collectors.base_collector import BaseCollector
from config.settings import (
    CHROME_CLIENT_ID,
    CHROME_CLIENT_SECRET,
    CHROME_REFRESH_TOKEN,
    DATA_DIR,
)
from storage.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)

LAST_COLLECTED_FILE = os.path.join(DATA_DIR, "chrome_last_collected.txt")

# Default Chrome History DB locations per platform
_CHROME_HISTORY_PATHS = {
    "linux": os.path.expanduser(
        "~/.config/google-chrome/Default/History"
    ),
    "darwin": os.path.expanduser(
        "~/Library/Application Support/Google/Chrome/Default/History"
    ),
    "win32": os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Default", "History"
    ),
}


class ChromeCollector(BaseCollector):
    """Collector that gathers browsing history from Google Chrome.

    Two strategies are supported:

    1. **OAuth2 API** -- Uses the Chrome History Sync API with an OAuth2
       access token.  Requires ``CHROME_CLIENT_ID``, ``CHROME_CLIENT_SECRET``,
       and ``CHROME_REFRESH_TOKEN`` to be configured.

    2. **Local SQLite fallback** -- Copies and reads the Chrome profile's
       ``History`` SQLite database directly.  This works without any API
       credentials but requires that Chrome is installed locally.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        super().__init__(sqlite_manager)
        self._access_token: Optional[str] = None
        self._last_collected_path: str = LAST_COLLECTED_FILE

    @property
    def source(self) -> str:
        return "chrome"

    # ------------------------------------------------------------------
    # Timestamp tracking
    # ------------------------------------------------------------------

    def _read_last_collected(self) -> Optional[datetime]:
        """Read the last collection timestamp from disk."""
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
        """Persist the latest collection timestamp to disk."""
        try:
            path = Path(self._last_collected_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(ts.isoformat())
        except Exception as exc:
            self.logger.warning("Could not write last collected timestamp: %s", exc)

    # ------------------------------------------------------------------
    # OAuth2 token management
    # ------------------------------------------------------------------

    def _refresh_access_token(self) -> Optional[str]:
        """Refresh the OAuth2 access token using the stored refresh token.

        Returns:
            A fresh access token string, or None on failure.
        """
        if not all([CHROME_CLIENT_ID, CHROME_CLIENT_SECRET, CHROME_REFRESH_TOKEN]):
            self.logger.debug(
                "Chrome OAuth credentials not fully configured; "
                "skipping token refresh."
            )
            return None

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": CHROME_CLIENT_ID,
            "client_secret": CHROME_CLIENT_SECRET,
            "refresh_token": CHROME_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(token_url, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token")
            self.logger.debug("Chrome OAuth access token refreshed successfully.")
            return self._access_token
        except requests.RequestException as exc:
            self.logger.error("Failed to refresh Chrome access token: %s", exc)
            return None

    # ------------------------------------------------------------------
    # API-based collection
    # ------------------------------------------------------------------

    def _collect_via_api(self) -> Optional[List[Dict[str, Any]]]:
        """Attempt to collect browsing history via the Chrome History Sync API.

        Returns:
            A list of normalised events, or None if the API approach fails
            or is not configured.
        """
        token = self._refresh_access_token()
        if not token:
            return None

        # NOTE: Chrome History API access may need an alternative approach.
        # Google does not currently expose a public REST API for browsing
        # history.  The URL below is a placeholder for custom OAuth clients
        # that have been granted the appropriate scope.
        history_url = "https://history.google.com/history/feeds/lookup"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(history_url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            self.logger.warning("Chrome History API request failed: %s", exc)
            return None

        last_collected = self._read_last_collected()
        events: List[Dict[str, Any]] = []

        for item in data.get("event", []):
            url = item.get("url", "")
            title = item.get("title", "")
            visit_time_usec = item.get("time_usec", 0)

            try:
                visit_dt = datetime.fromtimestamp(
                    visit_time_usec / 1_000_000, tz=timezone.utc
                )
            except (OSError, ValueError):
                continue

            if last_collected and visit_dt <= last_collected:
                continue

            events.append(
                {
                    "source": self.source,
                    "event_type": "page_view",
                    "timestamp": visit_dt.isoformat(),
                    "data": {
                        "url": url,
                        "title": title,
                        "visit_time": visit_dt.isoformat(),
                    },
                }
            )

        return events

    # ------------------------------------------------------------------
    # Local SQLite fallback
    # ------------------------------------------------------------------

    def _detect_chrome_history_path(self) -> Optional[str]:
        """Detect the Chrome History SQLite database path for this platform."""
        import sys

        platform = sys.platform
        path = _CHROME_HISTORY_PATHS.get(platform)
        if path and os.path.isfile(path):
            return path
        self.logger.debug("Chrome History DB not found at expected path: %s", path)
        return None

    def _collect_via_sqlite(self) -> Optional[List[Dict[str, Any]]]:
        """Collect browsing history by reading the local Chrome History DB.

        Chrome locks its database while running, so we copy it to a
        temporary location before reading.

        Returns:
            A list of normalised events, or None if the DB cannot be read.
        """
        db_path = self._detect_chrome_history_path()
        if not db_path:
            return None

        # Copy the database to avoid locking issues
        tmp_dir = tempfile.mkdtemp(prefix="chrome_history_")
        tmp_db = os.path.join(tmp_dir, "History")
        try:
            shutil.copy2(db_path, tmp_db)
        except OSError as exc:
            self.logger.error("Could not copy Chrome History DB: %s", exc)
            return None

        last_collected = self._read_last_collected()
        events: List[Dict[str, Any]] = []

        try:
            conn = sqlite3.connect(tmp_db)
            cursor = conn.cursor()

            # Chrome stores timestamps as microseconds since 1601-01-01
            # (Windows FILETIME epoch).  Delta to Unix epoch in microseconds:
            _EPOCH_DELTA_USEC = 11_644_473_600_000_000

            query = """
                SELECT u.url, u.title, v.visit_time
                FROM visits v
                JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
                LIMIT 500
            """
            cursor.execute(query)

            for url, title, visit_time_chrome in cursor.fetchall():
                try:
                    unix_usec = visit_time_chrome - _EPOCH_DELTA_USEC
                    visit_dt = datetime.fromtimestamp(
                        unix_usec / 1_000_000, tz=timezone.utc
                    )
                except (OSError, ValueError):
                    continue

                if last_collected and visit_dt <= last_collected:
                    continue

                events.append(
                    {
                        "source": self.source,
                        "event_type": "page_view",
                        "timestamp": visit_dt.isoformat(),
                        "data": {
                            "url": url,
                            "title": title,
                            "visit_time": visit_dt.isoformat(),
                        },
                    }
                )

            conn.close()
        except sqlite3.Error as exc:
            self.logger.error("Error reading Chrome History DB: %s", exc)
            return None
        finally:
            # Clean up temporary copy
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return events

    # ------------------------------------------------------------------
    # Main collect
    # ------------------------------------------------------------------

    def collect(self) -> List[Dict[str, Any]]:
        """Collect recent Chrome browsing history events.

        Tries the OAuth2 API first; falls back to direct SQLite reading
        if the API is not configured or fails.

        Returns:
            A list of normalised event dictionaries.
        """
        # Strategy 1: OAuth2 API
        events = self._collect_via_api()
        if events is not None:
            self.logger.info(
                "Collected %d event(s) via Chrome History API.", len(events)
            )
            if events:
                self._write_last_collected(datetime.now(timezone.utc))
            return events

        # Strategy 2: Direct SQLite fallback
        self.logger.info(
            "Chrome API unavailable; falling back to local History DB."
        )
        events = self._collect_via_sqlite()
        if events is not None:
            self.logger.info(
                "Collected %d event(s) from local Chrome History DB.", len(events)
            )
            if events:
                self._write_last_collected(datetime.now(timezone.utc))
            return events

        self.logger.warning("Could not collect Chrome history via any method.")
        return []
