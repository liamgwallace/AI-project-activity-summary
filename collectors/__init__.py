"""Collectors module for PAIS - Data collection from various sources."""

from collectors.base import BaseCollector
from collectors.github_collector import GitHubCollector
from collectors.gmail_collector import GmailCollector
from collectors.calendar_collector import CalendarCollector
from collectors.browser_receiver import BrowserReceiver
from collectors.youtube_collector import YouTubeCollector

__all__ = [
    "BaseCollector",
    "GitHubCollector",
    "GmailCollector",
    "CalendarCollector",
    "BrowserReceiver",
    "YouTubeCollector",
]
