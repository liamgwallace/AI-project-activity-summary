"""Gmail activity collector.

Fetches recent emails from the authenticated user's Gmail inbox using
the Gmail API (via google-api-python-client).  Emails received within
the configured look-back window are normalised into activity events.
"""

import base64
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource

from collectors.base_collector import BaseCollector
from config.settings import DATA_DIR, GMAIL_CREDENTIALS_JSON
from storage.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the token file and re-authorise.
_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_TOKEN_PATH = os.path.join(DATA_DIR, "gmail_token.json")


class GmailCollector(BaseCollector):
    """Collector that fetches recent emails from Gmail.

    Uses the Gmail API v1 with OAuth2 credentials.  On the first run
    the user is prompted to authorise via the browser; subsequent runs
    use a cached token that is refreshed automatically.

    Configuration:
        ``GMAIL_CREDENTIALS_JSON`` must point to the path of the OAuth
        client secrets JSON file downloaded from the Google Cloud Console.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        super().__init__(sqlite_manager)
        self._service: Optional[Resource] = None

    @property
    def source(self) -> str:
        return "gmail"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_credentials(self) -> Optional[Credentials]:
        """Load or create OAuth2 credentials for the Gmail API.

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
                self.logger.warning("Could not load cached Gmail token: %s", exc)

        # Refresh or create new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                self.logger.error("Failed to refresh Gmail token: %s", exc)
                creds = None

        if not creds or not creds.valid:
            if not GMAIL_CREDENTIALS_JSON or not os.path.exists(GMAIL_CREDENTIALS_JSON):
                self.logger.error(
                    "GMAIL_CREDENTIALS_JSON is not set or file does not exist: %s",
                    GMAIL_CREDENTIALS_JSON,
                )
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_JSON, _SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as exc:
                self.logger.error("Gmail OAuth flow failed: %s", exc)
                return None

        # Cache the token for future runs
        if creds:
            try:
                os.makedirs(os.path.dirname(_TOKEN_PATH), exist_ok=True)
                with open(_TOKEN_PATH, "w", encoding="utf-8") as fh:
                    fh.write(creds.to_json())
            except Exception as exc:
                self.logger.warning("Could not cache Gmail token: %s", exc)

        return creds

    def _get_service(self) -> Optional[Resource]:
        """Build and cache the Gmail API service resource.

        Returns:
            A ``googleapiclient.discovery.Resource`` for the Gmail API,
            or None on failure.
        """
        if self._service is not None:
            return self._service

        creds = self._get_credentials()
        if creds is None:
            return None

        try:
            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except Exception as exc:
            self.logger.error("Failed to build Gmail API service: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_header(headers: List[Dict[str, str]], name: str) -> str:
        """Extract a single header value from a Gmail message headers list."""
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value", "")
        return ""

    def _fetch_message_detail(
        self, service: Resource, msg_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch and normalise a single Gmail message.

        Args:
            service: The Gmail API service resource.
            msg_id: The Gmail message ID.

        Returns:
            A normalised event dictionary, or None on failure.
        """
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="metadata")
                .execute()
            )
        except Exception as exc:
            self.logger.warning("Failed to fetch Gmail message %s: %s", msg_id, exc)
            return None

        headers = msg.get("payload", {}).get("headers", [])
        subject = self._get_header(headers, "Subject")
        sender = self._get_header(headers, "From")
        date_str = self._get_header(headers, "Date")
        snippet = msg.get("snippet", "")

        # Parse internal date (millis since epoch)
        internal_date_ms = int(msg.get("internalDate", 0))
        try:
            event_dt = datetime.fromtimestamp(
                internal_date_ms / 1000, tz=timezone.utc
            )
        except (OSError, ValueError):
            event_dt = datetime.now(timezone.utc)

        return {
            "source": self.source,
            "event_type": "email",
            "timestamp": event_dt.isoformat(),
            "data": {
                "subject": subject,
                "sender": sender,
                "snippet": snippet,
                "date": date_str,
            },
        }

    # ------------------------------------------------------------------
    # Main collect
    # ------------------------------------------------------------------

    def collect(self) -> List[Dict[str, Any]]:
        """Collect recent emails from Gmail (last hour).

        Returns:
            A list of normalised email event dictionaries.
        """
        service = self._get_service()
        if service is None:
            self.logger.error("Gmail service unavailable. Skipping collection.")
            return []

        # Build a query for messages received in the last hour
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        since_epoch = int(since.timestamp())
        query = f"after:{since_epoch}"

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=50)
                .execute()
            )
        except Exception as exc:
            self.logger.error("Failed to list Gmail messages: %s", exc)
            return []

        messages = results.get("messages", [])
        if not messages:
            self.logger.info("No new Gmail messages in the last hour.")
            return []

        self.logger.info("Found %d Gmail message(s) to process.", len(messages))

        events: List[Dict[str, Any]] = []
        for msg_stub in messages:
            msg_id = msg_stub.get("id", "")
            if not msg_id:
                continue
            event = self._fetch_message_detail(service, msg_id)
            if event is not None:
                events.append(event)

        return events
