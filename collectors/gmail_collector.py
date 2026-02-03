"""
Gmail data collector for PAIS.
Fetches emails from priority inbox using Gmail API.
"""

import os
import json
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from collectors.base import BaseCollector
from storage.database import Database

# Gmail API scopes
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailCollector(BaseCollector):
    """Collects Gmail activity (emails)."""
    
    def __init__(self, credentials_path: str):
        """Initialize with OAuth credentials path."""
        super().__init__("gmail")
        self.credentials_path = credentials_path
        self.token_path = self.settings.gmail.token_path
        self.service: Optional[Any] = None
        self.db = Database(self.settings.database.path)
        
        # Ensure config directory exists
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
        
        if credentials_path and Path(credentials_path).exists():
            try:
                self.service = self._get_service()
                self.logger.info("Initialized Gmail collector")
            except Exception as e:
                self.logger.error(f"Failed to initialize Gmail service: {e}")
        else:
            self.logger.warning(f"Gmail credentials not found at: {credentials_path}")
    
    def _get_service(self) -> Any:
        """Get or create Gmail API service with OAuth flow."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, GMAIL_SCOPES)
                self.logger.info("Loaded existing Gmail token")
            except Exception as e:
                self.logger.warning(f"Failed to load token: {e}")
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Refreshed Gmail token")
                except Exception as e:
                    self.logger.error(f"Failed to refresh token: {e}")
                    creds = None
            
            if not creds:
                # Run OAuth flow
                if not self.credentials_path or not Path(self.credentials_path).exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("Completed Gmail OAuth flow")
            
            # Save token for future runs
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                self.logger.info(f"Saved Gmail token to {self.token_path}")
        
        return build('gmail', 'v1', credentials=creds, cache_discovery=False)
    
    def _parse_email(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Gmail message into standardized event format."""
        try:
            headers = message.get("payload", {}).get("headers", [])
            
            # Extract headers
            subject = ""
            from_addr = ""
            to_addr = ""
            
            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                
                if name == "subject":
                    subject = value
                elif name == "from":
                    from_addr = value
                elif name == "to":
                    to_addr = value
            
            # Get internal date
            internal_date = message.get("internalDate")
            if internal_date:
                timestamp = datetime.fromtimestamp(int(internal_date) / 1000)
            else:
                timestamp = datetime.now()
            
            # Get snippet
            snippet = message.get("snippet", "")
            
            # Get labels
            labels = message.get("labelIds", [])
            
            # Get thread ID
            thread_id = message.get("threadId", "")
            
            return self._create_event(
                timestamp=timestamp,
                event_type="email",
                data={
                    "subject": subject,
                    "from": from_addr,
                    "to": to_addr,
                    "snippet": snippet,
                    "labels": labels,
                    "thread_id": thread_id,
                }
            )
            
        except Exception as e:
            self.logger.warning(f"Error parsing email: {e}")
            return None
    
    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        """Collect emails from priority inbox since the given date."""
        events = []
        
        if not self.service:
            self.logger.error("Gmail service not initialized")
            return events
        
        self.logger.info(f"Starting Gmail collection since {since.isoformat()}")
        
        try:
            # Build query for date range
            since_str = since.strftime("%Y/%m/%d")
            query = f"after:{since_str}"
            
            # Query for each configured label
            for label in self.settings.gmail.labels:
                self.logger.info(f"Querying label: {label}")
                
                try:
                    results = self.service.users().messages().list(
                        userId='me',
                        labelIds=[label],
                        q=query,
                        maxResults=100
                    ).execute()
                    
                    messages = results.get('messages', [])
                    self.logger.info(f"Found {len(messages)} messages in {label}")
                    
                    for msg_meta in messages:
                        try:
                            # Get full message details
                            msg = self.service.users().messages().get(
                                userId='me',
                                id=msg_meta['id']
                            ).execute()
                            
                            event = self._parse_email(msg)
                            if event:
                                events.append(event)
                                
                        except Exception as e:
                            self.logger.warning(f"Error fetching message {msg_meta['id']}: {e}")
                            continue
                            
                except Exception as e:
                    self.logger.error(f"Error querying label {label}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error collecting Gmail data: {e}")
        
        self.logger.info(f"Gmail collection complete. Total events: {len(events)}")
        return events
    
    def test(self) -> Dict[str, Any]:
        """Test the collector by fetching sample recent emails."""
        result = {
            "success": False,
            "message": "",
            "sample_events": [],
        }
        
        if not self.service:
            result["message"] = "Gmail service not initialized - check credentials"
            return result
        
        try:
            # Get recent emails (last 3 days)
            since = datetime.now() - timedelta(days=3)
            sample_events = self.collect(since)
            
            # Limit to first 5 events
            result["sample_events"] = sample_events[:5]
            result["success"] = True
            result["message"] = f"Found {len(sample_events)} emails in the last 3 days"
            
        except Exception as e:
            result["message"] = f"Test failed: {str(e)}"
            self.logger.error(f"Gmail collector test failed: {e}")
        
        return result
