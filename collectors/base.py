"""
Abstract base collector class for PAIS.
Defines the interface all collectors must implement.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any
import logging
from pathlib import Path

from config.settings import get_settings


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""
    
    def __init__(self, source_name: str):
        """Initialize the collector with logging setup."""
        self.source_name = source_name
        self.settings = get_settings()
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging to the appropriate log file."""
        logger = logging.getLogger(f"pais.collector.{self.source_name}")
        
        if not logger.handlers:
            log_dir = Path(self.settings.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"{self.source_name}.log"
            
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    @abstractmethod
    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        """
        Collect events from the source since the specified datetime.
        
        Args:
            since: Collect events from this datetime onwards
            
        Returns:
            List of event dictionaries with standardized structure
        """
        pass
    
    @abstractmethod
    def test(self) -> Dict[str, Any]:
        """
        Test the collector by fetching sample data.
        
        Returns:
            Dictionary with test results and sample data
        """
        pass
    
    def _create_event(self, timestamp: datetime, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a standardized event dictionary."""
        return {
            "timestamp": timestamp.isoformat(),
            "source": self.source_name,
            "event_type": event_type,
            "data": data,
        }
