"""Data collectors for the Personal Activity Intelligence System.

Each collector extends :class:`BaseCollector` and gathers activity data
from a specific source (GitHub, filesystem, Chrome, Gmail, Google
Calendar).
"""

from collectors.base_collector import BaseCollector
from collectors.github_collector import GitHubCollector
from collectors.filesystem_collector import FilesystemCollector
from collectors.chrome_collector import ChromeCollector
from collectors.gmail_collector import GmailCollector
from collectors.gcal_collector import GCalCollector

__all__ = [
    "BaseCollector",
    "GitHubCollector",
    "FilesystemCollector",
    "ChromeCollector",
    "GmailCollector",
    "GCalCollector",
]
