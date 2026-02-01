"""
Task definitions for the APScheduler.

Provides a TaskRunner class that encapsulates all scheduled task logic,
including data collection, session grouping, daily processing,
weekly synthesis, and cache cleanup.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskRunner:
    """Encapsulates all scheduled tasks for the activity intelligence system.

    Each method corresponds to a scheduled job and includes comprehensive
    error handling and logging to ensure the scheduler remains stable
    even when individual tasks encounter failures.
    """

    def __init__(
        self,
        collectors,
        session_grouper,
        daily_processor,
        weekly_synthesizer,
        cache_manager,
    ):
        """Initialize the TaskRunner with all required components.

        Args:
            collectors: Dictionary of collector instances keyed by name.
                Expected keys: 'github', 'chrome', 'gmail', 'gcal'.
                The 'filesystem' collector runs continuously and is not
                invoked by the scheduler.
            session_grouper: SessionGrouper instance for grouping
                raw activities into logical sessions.
            daily_processor: DailyProcessor instance for generating
                daily activity summaries.
            weekly_synthesizer: WeeklySynthesizer instance for
                generating weekly synthesis reports.
            cache_manager: CacheManager instance for managing
                cached data with TTL-based expiry.
        """
        self.collectors = collectors
        self.session_grouper = session_grouper
        self.daily_processor = daily_processor
        self.weekly_synthesizer = weekly_synthesizer
        self.cache_manager = cache_manager

    def run_collectors(self):
        """Run all data collectors sequentially.

        Executes each collector (github, chrome, gmail, gcal) in order.
        Individual collector failures are logged but do not prevent
        other collectors from running. The filesystem collector is
        excluded as it runs continuously in its own thread.
        """
        start_time = datetime.now()
        logger.info("Starting scheduled data collection run...")

        collector_names = ["github", "chrome", "gmail", "gcal"]
        results = {}

        for name in collector_names:
            collector = self.collectors.get(name)
            if collector is None:
                logger.warning(
                    "Collector '%s' not found. Skipping.", name
                )
                results[name] = "skipped"
                continue

            try:
                logger.info("Running %s collector...", name)
                result = collector.collect()
                results[name] = result
                logger.info(
                    "%s collector completed successfully: %s",
                    name.capitalize(),
                    result,
                )
            except Exception as e:
                results[name] = f"error: {e}"
                logger.error(
                    "Error running %s collector: %s",
                    name,
                    e,
                    exc_info=True,
                )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            "Data collection run completed in %.1f seconds. Results: %s",
            elapsed,
            results,
        )
        return results

    def run_session_grouping(self):
        """Run the session grouper to organize activities into sessions.

        Groups raw activity records into logical sessions based on
        temporal proximity and source context.
        """
        start_time = datetime.now()
        logger.info("Starting session grouping...")

        try:
            result = self.session_grouper.group_events()
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Session grouping completed in %.1f seconds: %s",
                elapsed,
                result,
            )
            return result
        except Exception as e:
            logger.error(
                "Error during session grouping: %s",
                e,
                exc_info=True,
            )
            return None

    def run_daily_processing(self):
        """Run the daily processor to generate activity summaries.

        Processes grouped sessions into daily summaries using AI-powered
        analysis, then writes the results to the Obsidian vault.
        """
        start_time = datetime.now()
        logger.info("Starting daily processing...")

        try:
            result = self.daily_processor.process()
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Daily processing completed in %.1f seconds: %s",
                elapsed,
                result,
            )
            return result
        except Exception as e:
            logger.error(
                "Error during daily processing: %s",
                e,
                exc_info=True,
            )
            return None

    def run_weekly_synthesis(self):
        """Run the weekly synthesizer to create weekly reports.

        Aggregates daily summaries into a comprehensive weekly report
        with insights, patterns, and recommendations.
        """
        start_time = datetime.now()
        logger.info("Starting weekly synthesis...")

        try:
            result = self.weekly_synthesizer.synthesize()
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Weekly synthesis completed in %.1f seconds: %s",
                elapsed,
                result,
            )
            return result
        except Exception as e:
            logger.error(
                "Error during weekly synthesis: %s",
                e,
                exc_info=True,
            )
            return None

    def run_cache_cleanup(self):
        """Clean up expired cache entries.

        Removes cache entries that have exceeded their TTL to prevent
        unbounded memory or storage growth.
        """
        start_time = datetime.now()
        logger.info("Starting cache cleanup...")

        try:
            result = self.cache_manager.cleanup_expired()
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Cache cleanup completed in %.1f seconds: %s",
                elapsed,
                result,
            )
            return result
        except Exception as e:
            logger.error(
                "Error during cache cleanup: %s",
                e,
                exc_info=True,
            )
            return None
