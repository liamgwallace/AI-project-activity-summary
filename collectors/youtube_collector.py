"""
YouTube data collector for PAIS.
Fetches liked videos from YouTube, filtering out Shorts.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from collectors.base import BaseCollector

# YouTube API scopes
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


class YouTubeCollector(BaseCollector):
    """Collects liked videos from YouTube, excluding Shorts."""

    def __init__(self, credentials_path: str):
        """Initialize with OAuth credentials path."""
        super().__init__("youtube")
        self.credentials_path = credentials_path
        self.token_path = self.settings.youtube.token_path
        self.service: Optional[Any] = None
        self.min_duration_seconds = self.settings.youtube.min_duration_seconds

        # Ensure config directory exists
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)

        if credentials_path and Path(credentials_path).exists():
            try:
                self.service = self._get_service()
                self.logger.info("Initialized YouTube collector")
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTube service: {e}")
        else:
            self.logger.warning(f"YouTube credentials not found at: {credentials_path}")

    def _get_service(self) -> Any:
        """Get or create YouTube API service with OAuth flow."""
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, YOUTUBE_SCOPES)
                self.logger.info("Loaded existing YouTube token")
            except Exception as e:
                self.logger.warning(f"Failed to load token: {e}")

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Refreshed YouTube token")
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
                    self.credentials_path, YOUTUBE_SCOPES
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("Completed YouTube OAuth flow")

            # Save token for future runs
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
                self.logger.info(f"Saved YouTube token to {self.token_path}")

        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def _is_short(self, video_id: str) -> bool:
        """Check if a video is a Short by examining its details."""
        try:
            video_response = (
                self.service.videos()
                .list(part="contentDetails,snippet", id=video_id)
                .execute()
            )

            if not video_response.get("items"):
                return False

            video = video_response["items"][0]
            content_details = video.get("contentDetails", {})
            duration = content_details.get("duration", "")

            # Parse ISO 8601 duration
            # PT1M30S = 1 minute 30 seconds
            # PT30S = 30 seconds
            duration_seconds = self._parse_duration(duration)

            return duration_seconds <= self.min_duration_seconds

        except Exception as e:
            self.logger.warning(f"Error checking if video {video_id} is a Short: {e}")
            return False

    def _parse_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration string to seconds."""
        import re

        if not duration:
            return 0

        # Match PT#H#M#S format
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if not match:
            return 0

        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0

        return hours * 3600 + minutes * 60 + seconds

    def _parse_video(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a liked video into standardized format."""
        try:
            snippet = item.get("snippet", {})
            video_id = item.get("contentDetails", {}).get("videoId", "")

            if not video_id:
                return None

            # Check if it's a short
            if self._is_short(video_id):
                self.logger.debug(f"Skipping Short video: {snippet.get('title', 'Unknown')}")
                return None

            # Parse published at
            published_at = snippet.get("publishedAt", "")
            try:
                timestamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except:
                timestamp = datetime.now()

            return self._create_event(
                timestamp=timestamp,
                event_type="video_like",
                data={
                    "video_id": video_id,
                    "title": snippet.get("title", "Unknown"),
                    "channel": snippet.get("channelTitle", "Unknown"),
                    "channel_id": snippet.get("channelId", ""),
                    "description": snippet.get("description", ""),
                    "url": f"https://youtube.com/watch?v={video_id}",
                }
            )

        except Exception as e:
            self.logger.warning(f"Error parsing video: {e}")
            return None

    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        """Collect liked videos since the given date, excluding Shorts."""
        events = []

        if not self.service:
            self.logger.error("YouTube service not initialized")
            return events

        self.logger.info(f"Starting YouTube collection since {since.isoformat()}")

        try:
            # Format datetime for API (RFC 3339)
            since_str = since.isoformat() + "Z"

            # Get liked videos
            playlist_id = "LL"  # "Liked Videos" playlist
            page_token = None
            total_checked = 0

            while True:
                # Query playlist items
                request = self.service.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token,
                )

                response = request.execute()
                items = response.get("items", [])

                if not items:
                    break

                for item in items:
                    total_checked += 1

                    # Check if video is after our cutoff
                    snippet = item.get("snippet", {})
                    published_at = snippet.get("publishedAt", "")

                    try:
                        video_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        # Make since timezone-aware for comparison
                        since_aware = since.replace(tzinfo=video_time.tzinfo) if since.tzinfo is None else since
                        if video_time < since_aware:
                            # Videos are returned in reverse chronological order
                            # So we can stop once we hit an old one
                            self.logger.info(f"Reached videos older than {since}, stopping")
                            break
                    except:
                        continue

                    # Parse and add event
                    parsed = self._parse_video(item)
                    if parsed:
                        events.append(parsed)

                else:
                    # Continue to next page if we didn't break
                    page_token = response.get("nextPageToken")
                    if not page_token:
                        break
                    continue

                break

            self.logger.info(f"YouTube collection complete. Checked {total_checked} videos, "
                           f"collected {len(events)} non-Short videos")

        except Exception as e:
            self.logger.error(f"Error collecting YouTube data: {e}")

        return events

    def test(self) -> Dict[str, Any]:
        """Test the collector by fetching recent liked videos."""
        result = {
            "success": False,
            "message": "",
            "sample_events": [],
        }

        if not self.service:
            result["message"] = "YouTube service not initialized - check credentials"
            return result

        try:
            # Get videos from last 7 days
            since = datetime.now() - timedelta(days=7)
            sample_events = self.collect(since)

            # Limit to first 5 events
            result["sample_events"] = sample_events[:5]
            result["success"] = True
            result["message"] = f"Found {len(sample_events)} liked videos in the last 7 days"

        except Exception as e:
            result["message"] = f"Test failed: {str(e)}"
            self.logger.error(f"YouTube collector test failed: {e}")

        return result
