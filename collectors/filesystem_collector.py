"""Filesystem activity collector.

Monitors configured directories for file creation, modification, and
deletion events using the *watchdog* library. Collected events are
queued in memory and drained on each collect() call.
"""

import fnmatch
import json
import logging
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from collectors.base_collector import BaseCollector
from config.settings import CONFIG_DIR, DATA_DIR
from storage.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)

MONITORED_PATHS_CONFIG = os.path.join(CONFIG_DIR, "monitored_paths.json")


class FileEventHandler(FileSystemEventHandler):
    """Watchdog event handler that queues filesystem events for later processing.

    Only file-level events are captured (directory events are ignored).
    Events matching any blacklist pattern are silently dropped.
    """

    def __init__(
        self,
        event_queue: "queue.Queue[FileSystemEvent]",
        blacklist_patterns: List[str],
    ) -> None:
        super().__init__()
        self._queue = event_queue
        self._blacklist_patterns = blacklist_patterns

    def _is_blacklisted(self, path: str) -> bool:
        """Check whether *path* matches any configured blacklist pattern."""
        basename = os.path.basename(path)
        for pattern in self._blacklist_patterns:
            if fnmatch.fnmatch(basename, pattern):
                return True
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._is_blacklisted(event.src_path):
            self._queue.put(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._is_blacklisted(event.src_path):
            self._queue.put(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._is_blacklisted(event.src_path):
            self._queue.put(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and not self._is_blacklisted(event.src_path):
            self._queue.put(event)


class FilesystemCollector(BaseCollector):
    """Collector that monitors local filesystem paths for file changes.

    Configuration is loaded from ``config/monitored_paths.json`` which should
    have the following structure::

        {
            "paths": ["/home/user/projects", "/home/user/notes"],
            "project_roots": {
                "my-project": "/home/user/projects/my-project",
                "notes": "/home/user/notes"
            },
            "blacklist_patterns": ["*.pyc", "__pycache__", ".git", "*.swp", "*.tmp"],
            "recursive": true
        }

    The observer runs in a background thread and accumulates events into a
    thread-safe queue.  Each call to ``collect()`` drains that queue and
    returns the events gathered since the last call.
    """

    def __init__(self, sqlite_manager: SQLiteManager) -> None:
        super().__init__(sqlite_manager)
        self._event_queue: queue.Queue[FileSystemEvent] = queue.Queue()
        self._observer: Optional[Observer] = None
        self._observer_lock = threading.Lock()
        self._config: Dict[str, Any] = self._load_config()

    @property
    def source(self) -> str:
        return "filesystem"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration from the JSON config file.

        Returns:
            A dictionary with keys ``paths``, ``project_roots``,
            ``blacklist_patterns``, and ``recursive``.
        """
        default_config: Dict[str, Any] = {
            "paths": [],
            "project_roots": {},
            "blacklist_patterns": [
                "*.pyc",
                "__pycache__",
                ".git",
                "*.swp",
                "*.tmp",
                ".DS_Store",
                "*.log",
            ],
            "recursive": True,
        }
        config_path = Path(MONITORED_PATHS_CONFIG)
        if not config_path.exists():
            self.logger.warning(
                "Monitored paths config not found at %s. Using defaults.",
                MONITORED_PATHS_CONFIG,
            )
            return default_config

        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            # Merge with defaults so missing keys are filled in
            for key, value in default_config.items():
                loaded.setdefault(key, value)
            return loaded
        except Exception as exc:
            self.logger.error("Failed to load monitored_paths.json: %s", exc)
            return default_config

    # ------------------------------------------------------------------
    # Observer management
    # ------------------------------------------------------------------

    def _start_observer(self) -> None:
        """Start the watchdog observer if it is not already running."""
        with self._observer_lock:
            if self._observer is not None and self._observer.is_alive():
                return

            paths: List[str] = self._config.get("paths", [])
            if not paths:
                self.logger.warning("No paths configured for filesystem monitoring.")
                return

            blacklist = self._config.get("blacklist_patterns", [])
            recursive = self._config.get("recursive", True)
            handler = FileEventHandler(self._event_queue, blacklist)

            self._observer = Observer()
            for path in paths:
                if os.path.isdir(path):
                    self._observer.schedule(handler, path, recursive=recursive)
                    self.logger.info("Watching path: %s (recursive=%s)", path, recursive)
                else:
                    self.logger.warning("Path does not exist, skipping: %s", path)

            self._observer.daemon = True
            self._observer.start()
            self.logger.info("Filesystem observer started.")

    def stop_observer(self) -> None:
        """Stop the watchdog observer if it is running."""
        with self._observer_lock:
            if self._observer is not None and self._observer.is_alive():
                self._observer.stop()
                self._observer.join(timeout=5)
                self.logger.info("Filesystem observer stopped.")
            self._observer = None

    # ------------------------------------------------------------------
    # Project matching
    # ------------------------------------------------------------------

    def match_project(self, filepath: str) -> Optional[str]:
        """Determine which project a file belongs to based on project_roots.

        Args:
            filepath: The absolute path of the file.

        Returns:
            The project name if the file is under a known project root,
            otherwise ``None``.
        """
        project_roots: Dict[str, str] = self._config.get("project_roots", {})
        abs_path = os.path.abspath(filepath)

        best_match: Optional[str] = None
        best_length = 0

        for project_name, root in project_roots.items():
            abs_root = os.path.abspath(root)
            if abs_path.startswith(abs_root + os.sep) or abs_path == abs_root:
                # Prefer the longest (most specific) matching root
                if len(abs_root) > best_length:
                    best_match = project_name
                    best_length = len(abs_root)

        return best_match

    # ------------------------------------------------------------------
    # Event type mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_event_type(event: FileSystemEvent) -> str:
        """Map a watchdog event to a human-readable event type string."""
        if isinstance(event, FileCreatedEvent):
            return "file_create"
        if isinstance(event, FileDeletedEvent):
            return "file_delete"
        if isinstance(event, FileModifiedEvent):
            return "file_edit"
        if isinstance(event, FileMovedEvent):
            return "file_move"
        return "file_edit"

    # ------------------------------------------------------------------
    # Main collect
    # ------------------------------------------------------------------

    def collect(self) -> List[Dict[str, Any]]:
        """Drain the internal event queue and return normalised events.

        The observer is started automatically on the first call if it is
        not already running.

        Returns:
            A list of normalised event dictionaries.
        """
        self._start_observer()

        events: List[Dict[str, Any]] = []
        while True:
            try:
                fs_event: FileSystemEvent = self._event_queue.get_nowait()
            except queue.Empty:
                break

            event_type = self._map_event_type(fs_event)
            filepath = fs_event.src_path
            project_name = self.match_project(filepath)

            events.append(
                {
                    "source": self.source,
                    "event_type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "path": filepath,
                        "event_type": event_type,
                        "project_name": project_name,
                    },
                }
            )

        return events
