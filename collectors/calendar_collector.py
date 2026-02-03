"""
Calendar data collector for PAIS.
Fetches events from primary Google Calendar.
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from collectors.base import BaseCollector
from storage.database import Database

# Calendar API scopes
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class CalendarCollector(BaseCollector):
    """Collects calendar events from Google Calendar."""
    
    def __init__(self, credentials_path: str):
        """Initialize with OAuth credentials path."""
        super().__init__("calendar")
        self.credentials_path = credentials_path
        self.token_path = self.settings.calendar.token_path
        self.service: Optional[Any] = None
        self.db = Database(self.settings.database.path)
        
        # Ensure config directory exists
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
        
        if credentials_path and Path(credentials_path).exists():
            try:
                self.service = self._get_service()
                self.logger.info("Initialized Calendar collector")
            except Exception as e:
                self.logger.error(f"Failed to initialize Calendar service: {e}")
        else:
            self.logger.warning(f"Calendar credentials not found at: {credentials_path}")
    
    def _get_service(self) -> Any:
        """Get or create Calendar API service with OAuth flow."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, CALENDAR_SCOPES)
                self.logger.info("Loaded existing Calendar token")
            except Exception as e:
                self.logger.warning(f"Failed to load token: {e}")
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Refreshed Calendar token")
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
                    self.credentials_path, CALENDAR_SCOPES
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("Completed Calendar OAuth flow")
            
            # Save token for future runs
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                self.logger.info(f"Saved Calendar token to {self.token_path}")
        
        return build('calendar', 'v3', credentials=creds, cache_discovery=False)
    
    def _parse_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Calendar event into standardized format."""
        try:
            # Get event times
            start = event.get("start", {})
            end = event.get("end", {})
            
            # Handle different datetime formats
            start_time = None
            end_time = None
            
            if "dateTime" in start:
                start_time = datetime.fromisoformat(start["dateTime"].replace('Z', '+00:00'))
            elif "date" in start:
                start_time = datetime.strptime(start["date"], "%Y-%m-%d")
            
            if "dateTime" in end:
                end_time = datetime.fromisoformat(end["dateTime"].replace('Z', '+00:00'))
            elif "date" in end:
                end_time = datetime.strptime(end["date"], "%Y-%m-%d")
            
            if not start_time:
                return None
            
            # Get attendees
            attendees = []
            for attendee in event.get("attendees", []):
                email = attendee.get("email", "")
                if email:
                    attendees.append(email)
            
            return self._create_event(
                timestamp=start_time,
                event_type="calendar_event",
                data={
                    "title": event.get("summary", "Untitled"),
                    "start": start_time.isoformat() if start_time else "",
                    "end": end_time.isoformat() if end_time else "",
                    "description": event.get("description", ""),
                    "location": event.get("location", ""),
                    "attendees": attendees,
                    "calendar_id": event.get("organizer", {}).get("email", "primary"),
                }
            )
            
        except Exception as e:
            self.logger.warning(f"Error parsing calendar event: {e}")
            return None
    
    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        """Collect events from primary calendar since the given date."""
        events = []
        
        if not self.service:
            self.logger.error("Calendar service not initialized")
            return events
        
        self.logger.info(f"Starting Calendar collection since {since.isoformat()}")
        
        try:
            # Determine which calendars to query
            calendars_to_query = self.settings.calendar.calendars or ["primary"]
            
            for calendar_id in calendars_to_query:
                self.logger.info(f"Querying calendar: {calendar_id}")
                
                try:
                    # Query events
                    time_min = since.isoformat()
                    
                    results = self.service.events().list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        maxResults=100,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    
                    calendar_events = results.get('items', [])
                    self.logger.info(f"Found {len(calendar_events)} events in {calendar_id}")
                    
                    for event in calendar_events:
                        try:
                            parsed = self._parse_event(event)
                            if parsed:
                                events.append(parsed)
                        except Exception as e:
                            self.logger.warning(f"Error processing event: {e}")
                            continue
                            
                except Exception as e:
                    self.logger.error(f"Error querying calendar {calendar_id}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error collecting Calendar data: {e}")
        
        self.logger.info(f"Calendar collection complete. Total events: {len(events)}")
        return events
    
    def test(self) -> Dict[str, Any]:
        """Test the collector by fetching upcoming events."""
        result = {
            "success": False,
            "message": "",
            "sample_events": [],
        }
        
        if not self.service:
            result["message"] = "Calendar service not initialized - check credentials"
            return result
        
        try:
            # Get upcoming events (next 7 days)
            since = datetime.now()
            until = since + timedelta(days=7)
            
            # Collect events
            sample_events = self.collect(since)
            
            # Filter to only future events within 7 days
            upcoming = []
            for event in sample_events:
                try:
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time <= until:
                        upcoming.append(event)
                except:
                    continue
            
            # Limit to first 5 events
            result["sample_events"] = upcoming[:5]
            result["success"] = True
            result["message"] = f"Found {len(upcoming)} upcoming events in the next 7 days"
            
        except Exception as e:
            result["message"] = f"Test failed: {str(e)}"
            self.logger.error(f"Calendar collector test failed: {e}")
        
        return result
