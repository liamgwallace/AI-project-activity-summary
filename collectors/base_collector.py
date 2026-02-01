"""Base collector module providing the abstract interface for all data collectors."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from storage.sqlite_manager import SQLiteManager


class BaseCollector(ABC):
    """Abstract base class for all activity data collectors.

    Provides a common interface and shared functionality for collectors
    that gather activity data from various sources (GitHub, filesystem,
    browser history, email, calendar, etc.).

    Subclasses must implement:
        - collect(): Gather raw events from the data source.
        - source: A property returning the string name of the source.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        """Initialize the collector with a storage backend.

        Args:
            sqlite_manager: An SQLiteManager instance used to persist
                collected events into the local SQLite database.
        """
        self.sqlite_manager = sqlite_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def source(self) -> str:
        """Return the string identifier for this collector's data source.

        Examples: 'github', 'filesystem', 'chrome', 'gmail', 'calendar'.
        """
        ...

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """Collect activity events from the data source.

        Returns:
            A list of event dictionaries. Each dictionary should contain
            at minimum the keys expected by SQLiteManager.insert_event:
                - source (str): The data source name.
                - event_type (str): The type of event.
                - data (dict): Arbitrary payload describing the event.
                - timestamp (str): ISO-8601 timestamp of when the event occurred.
        """
        ...

    def store_events(self, events: List[Dict[str, Any]]) -> int:
        """Persist a list of collected events to the SQLite database.

        Args:
            events: A list of event dictionaries to store. Each dict should
                contain 'timestamp', 'source', 'event_type', and 'data' keys.

        Returns:
            The number of events successfully stored.
        """
        stored = 0
        for event in events:
            try:
                self.sqlite_manager.insert_event(
                    timestamp=event["timestamp"],
                    source=event["source"],
                    event_type=event["event_type"],
                    data=event.get("data", {}),
                )
                stored += 1
            except Exception as exc:
                self.logger.error(
                    "Failed to store event from source '%s': %s",
                    self.source,
                    exc,
                )
        return stored

    def run(self) -> int:
        """Execute the full collection pipeline: collect then store.

        This is the main entry point for running a collector. It calls
        collect() to gather events, then store_events() to persist them.

        Returns:
            The number of events successfully stored, or 0 on failure.
        """
        self.logger.info("Starting collection for source '%s'.", self.source)
        try:
            events = self.collect()
            self.logger.info(
                "Collected %d event(s) from source '%s'.",
                len(events),
                self.source,
            )
        except Exception as exc:
            self.logger.error(
                "Error during collection for source '%s': %s",
                self.source,
                exc,
                exc_info=True,
            )
            return 0

        if not events:
            self.logger.info("No new events from source '%s'.", self.source)
            return 0

        try:
            stored = self.store_events(events)
            self.logger.info(
                "Stored %d/%d event(s) for source '%s'.",
                stored,
                len(events),
                self.source,
            )
            return stored
        except Exception as exc:
            self.logger.error(
                "Error storing events for source '%s': %s",
                self.source,
                exc,
                exc_info=True,
            )
            return 0
