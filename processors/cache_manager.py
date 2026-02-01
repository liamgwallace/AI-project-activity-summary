"""
Cache manager for webpage summaries in the Personal Activity Intelligence System.

Provides a caching layer between URL fetching/AI summarization and the rest
of the system. Summaries are stored in SQLite with configurable expiry to
avoid redundant API calls and page fetches.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from config import settings
from utils.fetch_page_content import fetch_page_content_sync

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages cached webpage summaries using SQLite storage.

    Before sending a URL to the AI for summarization, the cache is checked.
    If a valid (non-expired) summary exists, it is returned directly.
    Otherwise, the page content is fetched, summarized by the AI, and
    the result is cached for future use.

    Attributes:
        sqlite_manager: The SQLite database manager instance.
        ai_client: The AI client used for content summarization.
        cache_expiry_days: Number of days before a cached summary expires.
    """

    def __init__(self, sqlite_manager, ai_client) -> None:
        """Initialize the CacheManager.

        Args:
            sqlite_manager: SQLite database manager providing query and
                execute methods for the cache table.
            ai_client: AI client instance with a summarize or similar
                method for generating webpage summaries.
        """
        self.sqlite_manager = sqlite_manager
        self.ai_client = ai_client
        self.cache_expiry_days = getattr(settings, "CACHE_EXPIRY_DAYS", 7)
        logger.info(
            "CacheManager initialized with cache_expiry_days=%d",
            self.cache_expiry_days,
        )

    def get_or_create_summary(self, url: str, title: Optional[str] = None) -> str:
        """Get a cached summary for a URL, or create one if not cached.

        Checks the SQLite cache for a non-expired summary. If found,
        returns it directly. If not found or expired, fetches the page
        content, sends it to the AI for summarization, caches the result,
        and returns the summary.

        Args:
            url: The URL of the webpage to summarize.
            title: Optional page title to help the AI produce a better
                summary. If not provided, only the URL and content are used.

        Returns:
            A text summary of the webpage content. Returns an empty string
            if both cache lookup and fresh summarization fail.
        """
        if not url:
            logger.warning("Empty URL provided to get_or_create_summary")
            return ""

        logger.debug("Getting summary for URL: %s", url)

        # Check cache first
        cached = self._get_cached_summary(url)
        if cached is not None:
            logger.debug("Cache hit for URL: %s", url)
            return cached

        logger.debug("Cache miss for URL: %s, fetching and summarizing", url)

        # Fetch page content
        content = fetch_page_content_sync(url)
        if not content:
            logger.warning("Could not fetch content for URL: %s", url)
            return ""

        # Generate summary via AI
        try:
            summary = self.ai_client.summarize_webpage(
                url=url,
                content=content,
                title=title,
            )

            if summary:
                self._cache_summary(url, title, summary)
                logger.debug(
                    "Created and cached summary (%d chars) for URL: %s",
                    len(summary),
                    url,
                )
                return summary
            else:
                logger.warning("AI returned empty summary for URL: %s", url)
                return ""

        except Exception as e:
            logger.error(
                "Error generating summary for URL %s: %s", url, str(e)
            )
            return ""

    def _get_cached_summary(self, url: str) -> Optional[str]:
        """Look up a cached summary for the given URL.

        Args:
            url: The URL to look up.

        Returns:
            The cached summary string if found and not expired, None otherwise.
        """
        expiry_cutoff = datetime.utcnow() - timedelta(
            days=self.cache_expiry_days
        )
        expiry_str = expiry_cutoff.isoformat()

        try:
            results = self.sqlite_manager.query(
                """
                SELECT summary, cached_at
                FROM webpage_cache
                WHERE url = ? AND cached_at > ?
                ORDER BY cached_at DESC
                LIMIT 1
                """,
                (url, expiry_str),
            )

            if results:
                return results[0]["summary"]
            return None

        except Exception as e:
            logger.error("Error checking cache for URL %s: %s", url, str(e))
            return None

    def _cache_summary(
        self, url: str, title: Optional[str], summary: str
    ) -> None:
        """Store a summary in the cache.

        Uses INSERT OR REPLACE to update existing entries for the same URL.

        Args:
            url: The URL of the summarized page.
            title: The page title, if available.
            summary: The AI-generated summary text.
        """
        cached_at = datetime.utcnow().isoformat()

        try:
            self.sqlite_manager.execute(
                """
                INSERT OR REPLACE INTO webpage_cache
                    (url, title, summary, cached_at)
                VALUES (?, ?, ?, ?)
                """,
                (url, title or "", summary, cached_at),
            )
            logger.debug("Cached summary for URL: %s", url)
        except Exception as e:
            logger.error("Error caching summary for URL %s: %s", url, str(e))

    def cleanup_expired(self) -> int:
        """Delete expired cache entries from the database.

        Removes all entries where cached_at is older than the configured
        CACHE_EXPIRY_DAYS threshold.

        Returns:
            The number of expired entries deleted.
        """
        expiry_cutoff = datetime.utcnow() - timedelta(
            days=self.cache_expiry_days
        )
        expiry_str = expiry_cutoff.isoformat()

        try:
            result = self.sqlite_manager.execute(
                """
                DELETE FROM webpage_cache
                WHERE cached_at <= ?
                """,
                (expiry_str,),
            )

            deleted_count = getattr(result, "rowcount", 0)
            logger.info(
                "Cleaned up %d expired cache entries (older than %s)",
                deleted_count,
                expiry_str,
            )
            return deleted_count

        except Exception as e:
            logger.error("Error cleaning up expired cache entries: %s", str(e))
            return 0
