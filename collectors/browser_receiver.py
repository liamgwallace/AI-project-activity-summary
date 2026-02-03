"""
Browser activity receiver for PAIS.
Handles incoming page visit data from browser extension.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from collectors.base import BaseCollector
from storage.database import Database


class BrowserReceiver(BaseCollector):
    """Receives and stores browser activity events."""
    
    def __init__(self):
        """Initialize the browser receiver."""
        super().__init__("browser")
        self.db = Database(self.settings.database.path)
        self.logger.info("Initialized Browser receiver")
    
    def receive_page_visit(
        self,
        url: str,
        title: str,
        timestamp: datetime,
        device: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Receive and store a page visit event.
        
        Args:
            url: The visited URL
            title: The page title
            timestamp: When the visit occurred
            device: Device identifier (e.g., 'chrome-desktop', 'firefox-laptop')
            api_key: API key for authentication (validated against settings)
            
        Returns:
            Dictionary with success status and message
        """
        result = {
            "success": False,
            "message": "",
            "event_id": None,
        }
        
        # Validate API key if configured
        expected_key = getattr(self.settings, 'api_key', None)
        if expected_key and api_key != expected_key:
            result["message"] = "Invalid API key"
            self.logger.warning(f"Invalid API key received for page visit: {url}")
            return result
        
        try:
            # Create event
            event = self._create_event(
                timestamp=timestamp,
                event_type="page_visit",
                data={
                    "url": url,
                    "title": title,
                    "device": device,
                }
            )
            
            # Store in database
            event_id = self.db.insert_event(
                source=event["source"],
                event_type=event["event_type"],
                raw_data=json.dumps(event["data"]),
                event_time=event["timestamp"]
            )
            
            result["success"] = True
            result["message"] = "Page visit recorded"
            result["event_id"] = event_id
            
            self.logger.info(f"Recorded page visit: {url} (ID: {event_id})")
            
        except Exception as e:
            result["message"] = f"Failed to record page visit: {str(e)}"
            self.logger.error(f"Error recording page visit: {e}")
        
        return result
    
    def collect(self, since: datetime) -> list:
        """
        Collect browser events from database since the given date.
        
        Note: Browser events are received via receive_page_visit(),
        but this method allows querying stored events.
        """
        return self.db.get_events_since(since)
    
    def test(self) -> Dict[str, Any]:
        """Test the receiver by recording a sample event."""
        result = {
            "success": False,
            "message": "",
            "sample_event": None,
        }
        
        try:
            # Record a test page visit
            test_result = self.receive_page_visit(
                url="https://example.com/test",
                title="Test Page",
                timestamp=datetime.now(),
                device="test-device"
            )
            
            if test_result["success"]:
                result["success"] = True
                result["message"] = "Browser receiver test successful"
                result["sample_event"] = {
                    "url": "https://example.com/test",
                    "title": "Test Page",
                    "device": "test-device",
                    "event_id": test_result["event_id"],
                }
            else:
                result["message"] = test_result["message"]
                
        except Exception as e:
            result["message"] = f"Test failed: {str(e)}"
            self.logger.error(f"Browser receiver test failed: {e}")
        
        return result
