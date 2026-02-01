"""Google Calendar activity collector.

Fetches upcoming and recent calendar events from Google Calendar using
the Calendar API v3 (via google-api-python-client).  Events are
normalised into activity events for the summary pipeline.
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource

from collectors.base_collector import BaseCollector
from config.settings import DATA_DIR, GCAL_CREDENTIALS_JSON
from storage.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the token file and re-authorise.
_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_TOKEN_PATH = os.path.join(DATA_DIR, "gcal_token.json")


class GCalCollector(BaseCollector):
    """Collector that fetches events from Google Calendar.

    Uses the Google Calendar API v3 with OAuth2 credentials.  On the
    first run the user is prompted to authorise via the browser;
    subsequent runs use a cached token that is refreshed automatically.

    Configuration:
        ``GCAL_CREDENTIALS_JSON`` must point to the path of the OAuth
        client secrets JSON file downloaded from the Google Cloud Console.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        super().__init__(sqlite_manager)
        self._service: Optional[Resource] = None

    @property
    def source(self) -> str:
        return "calendar"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_credentials(self) -> Optional[Credentials]:
        """Load or create OAuth2 credentials for the Calendar API.

        Returns:
            A valid ``Credentials`` object, or None if credentials
            cannot be obtained.
        """
        creds: Optional[Credentials] = None

        # Try to load existing token
        if os.path.exists(_TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)
            except Exception as exc:
                self.logger.warning("Could not load cached GCal token: %s", exc)

        # Refresh or create new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                self.logger.error("Failed to refresh GCal token: %s", exc)
                creds = None

        if not creds or not creds.valid:
            if not GCAL_CREDENTIALS_JSON or not os.path.exists(GCAL_CREDENTIALS_JSON):
                self.logger.error(
                    "GCAL_CREDENTIALS_JSON is not set or file does not exist: %s",
                    GCAL_CREDENTIALS_JSON,
                )
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GCAL_CREDENTIALS_JSON, _SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as exc:
                self.logger.error("GCal OAuth flow failed: %s", exc)
                return None

        # Cache the token for future runs
        if creds:
            try:
                os.makedirs(os.path.dirname(_TOKEN_PATH), exist_ok=True)
                with open(_TOKEN_PATH, "w", encoding="utf-8") as fh:
                    fh.write(creds.to_json())
            except Exception as exc:
                self.logger.warning("Could not cache GCal token: %s", exc)

        return creds

    def _get_service(self) -> Optional[Resource]:
        """Build and cache the Calendar API service resource.

        Returns:
            A ``googleapiclient.discovery.Resource`` for the Calendar API,
            or None on failure.
        """
        if self._service is not None:
            return self._service

        creds = self._get_credentials()
        if creds is None:
            return None

        try:
            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception as exc:
            self.logger.error("Failed to build Calendar API service: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Event parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_event_datetime(dt_field: Dict[str, str]) -> Optional[str]:
        """Extract an ISO-8601 datetime string from a Calendar event datetime field.

        Calendar events can use either ``dateTime`` (timed events) or
        ``date`` (all-day events).

        Args:
            dt_field: A dict like ``{"dateTime": "...", "timeZone": "..."}``
                or ``{"date": "2025-01-15"}``.

        Returns:
            An ISO-8601 string, or None if parsing fails.
        """
        if not dt_field:
            return None
        return dt_field.get("dateTime") or dt_field.get("date")

    def _normalise_event(self, cal_event: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a raw Google Calendar event into a normalised activity event.

        Args:
            cal_event: A single event resource from the Calendar API.

        Returns:
            A normalised event dictionary ready for storage.
        """
        title = cal_event.get("summary", "(no title)")
        description = cal_event.get("description", "")
        location = cal_event.get("location", "")

        start_raw = cal_event.get("start", {})
        end_raw = cal_event.get("end", {})
        start = self._parse_event_datetime(start_raw) or ""
        end = self._parse_event_datetime(end_raw) or ""

        # Use start as the event timestamp; fall back to creation time
        timestamp = start or cal_event.get("created", datetime.now(timezone.utc).isoformat())

        return {
            "source": self.source,
            "event_type": "calendar_event",
            "timestamp": timestamp,
            "data": {
                "title": title,
                "start": start,
                "end": end,
                "description": description,
                "location": location,
            },
        }

    # ------------------------------------------------------------------
    # Main collect
    # ------------------------------------------------------------------

    def collect(self) -> List[Dict[str, Any]]:
        """Collect upcoming and recent Google Calendar events.

        Fetches events from 24 hours ago through 24 hours from now,
        giving a window that captures both recent past and near-future
        events.

        Returns:
            A list of normalised calendar event dictionaries.
        """
        service = self._get_service()
        if service is None:
            self.logger.error("Calendar service unavailable. Skipping collection.")
            return []

        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(hours=24)).isoformat()
        time_max = (now + timedelta(hours=24)).isoformat()

        try:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=100,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as exc:
            self.logger.error("Failed to list Calendar events: %s", exc)
            return []

        cal_events = events_result.get("items", [])
        if not cal_events:
            self.logger.info("No calendar events found in the configured window.")
            return []

        self.logger.info("Found %d calendar event(s) to process.", len(cal_events))

        events: List[Dict[str, Any]] = []
        for cal_event in cal_events:
            try:
                events.append(self._normalise_event(cal_event))
            except Exception as exc:
                self.logger.warning(
                    "Failed to normalise calendar event '%s': %s",
                    cal_event.get("id", "unknown"),
                    exc,
                )

        return events
