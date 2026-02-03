"""
Batch manager for controlling when and how activities are processed.

Implements token-based and time-based batching logic to optimize
AI processing costs and efficiency.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from storage.database import Database, RawEvent
from config.settings import get_settings

logger = logging.getLogger(__name__)


class BatchManager:
    """
    Manages batch processing logic including token estimation,
    time thresholds, and event retrieval.
    """
    
    def __init__(
        self,
        db: Database,
        max_tokens: int = 8000,
        interval_hours: int = 24,
    ):
        """
        Initialize the batch manager.
        
        Args:
            db: Database instance for event storage
            max_tokens: Maximum tokens to process in a batch
            interval_hours: Minimum hours between processing runs
        """
        self.db = db
        self.max_tokens = max_tokens
        self.interval_hours = interval_hours
        logger.info(
            f"BatchManager initialized: max_tokens={max_tokens}, "
            f"interval_hours={interval_hours}"
        )
    
    def should_process(self) -> bool:
        """
        Check if processing should run based on token count and time interval.
        
        Returns:
            True if processing should occur, False otherwise
        """
        try:
            # Check time interval
            last_process = self.get_last_process_time()
            if last_process:
                time_since = datetime.now() - last_process
                min_interval = timedelta(hours=self.interval_hours)
                
                if time_since < min_interval:
                    logger.debug(
                        f"Skipping: only {time_since.total_seconds()/3600:.1f}h "
                        f"since last process (min: {self.interval_hours}h)"
                    )
                    return False
            
            # Check if there are events to process
            events = self.db.get_unprocessed_events(limit=1)
            if not events:
                logger.debug("No unprocessed events found")
                return False
            
            # Check token threshold
            batch_events = self.get_events_for_batch()
            if not batch_events:
                return False
                
            estimated_tokens = self.estimate_tokens(batch_events)
            
            # Process if we have significant tokens or many events
            if estimated_tokens >= 1000 or len(batch_events) >= 10:
                logger.info(
                    f"Processing triggered: {len(batch_events)} events, "
                    f"~{estimated_tokens} tokens"
                )
                return True
            
            logger.debug(
                f"Not enough to process: {len(batch_events)} events, "
                f"~{estimated_tokens} tokens"
            )
            return False
            
        except Exception as e:
            logger.error(f"Error checking if should process: {e}")
            return False
    
    def estimate_tokens(self, events: List[RawEvent]) -> int:
        """
        Estimate token count for a list of events.
        
        Uses a rough approximation: ~4 characters per token on average.
        
        Args:
            events: List of raw events to estimate
            
        Returns:
            Estimated token count
        """
        total_chars = 0
        
        for event in events:
            # Count characters in raw_data and metadata
            total_chars += len(event.raw_data)
            total_chars += len(event.source)
            total_chars += len(event.event_type)
            total_chars += len(event.event_time)
        
        # Rough approximation: 4 chars per token
        # Add overhead for prompt template (~500 tokens)
        estimated = (total_chars // 4) + 500
        
        logger.debug(f"Estimated {estimated} tokens for {len(events)} events")
        return estimated
    
    def get_events_for_batch(self, limit: Optional[int] = None) -> List[RawEvent]:
        """
        Get unprocessed events up to token limit.
        
        Args:
            limit: Maximum number of events to retrieve (default: batch size)
            
        Returns:
            List of raw events ready for processing
        """
        if limit is None:
            # Calculate limit based on token estimation
            # Assume average event is ~200 tokens
            limit = max(10, self.max_tokens // 200)
        
        try:
            events = self.db.get_unprocessed_events(limit=limit)
            
            # Verify we don't exceed token limit
            estimated = self.estimate_tokens(events)
            while estimated > self.max_tokens and len(events) > 10:
                # Remove last few events to fit within limit
                events = events[:-5]
                estimated = self.estimate_tokens(events)
            
            logger.info(f"Retrieved {len(events)} events for batch (~{estimated} tokens)")
            return events
            
        except Exception as e:
            logger.error(f"Error retrieving events for batch: {e}")
            return []
    
    def get_last_process_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the last successful processing batch.
        
        Returns:
            Datetime of last successful batch, or None if no batches exist
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT end_time
                FROM processing_batches
                WHERE status = 'completed'
                ORDER BY end_time DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row["end_time"]:
                return datetime.fromisoformat(row["end_time"])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last process time: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current batch manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            events = self.db.get_unprocessed_events(limit=1000)
            pending_count = len(events)
            estimated_tokens = self.estimate_tokens(events)
            last_process = self.get_last_process_time()
            
            return {
                "pending_events": pending_count,
                "estimated_tokens": estimated_tokens,
                "max_tokens": self.max_tokens,
                "interval_hours": self.interval_hours,
                "last_process_time": last_process.isoformat() if last_process else None,
                "ready_to_process": self.should_process(),
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "pending_events": 0,
                "estimated_tokens": 0,
                "error": str(e),
            }
