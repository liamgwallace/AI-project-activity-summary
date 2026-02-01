"""
Personal Activity Intelligence System - Main Entry Point

Orchestrates data collection, AI processing, and synthesis of personal
activity data from multiple sources into structured Obsidian notes
with optional tweet generation.
"""

import logging
import signal
import sys
import threading

from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.logging_config import setup_logging
from config.settings import settings
from storage.sqlite_manager import SQLiteManager
from storage.graph_manager import GraphManager
from storage.obsidian_writer import ObsidianWriter
from ai.langchain_client import AIClient
from processors.cache_manager import CacheManager
from processors.session_grouper import SessionGrouper
from processors.daily_processor import DailyProcessor
from processors.weekly_synthesizer import WeeklySynthesizer
from collectors.github_collector import GitHubCollector
from collectors.chrome_collector import ChromeCollector
from collectors.gmail_collector import GmailCollector
from collectors.gcal_collector import GCalCollector
from collectors.filesystem_collector import FilesystemCollector
from scheduler.tasks import TaskRunner

# Load environment variables from .env file
load_dotenv()

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)


def create_components():
    """Create and return all system components."""
    logger.info("Initializing system components...")

    # Storage
    sqlite_manager = SQLiteManager()
    graph_manager = GraphManager()
    obsidian_writer = ObsidianWriter()

    # AI Client
    ai_client = AIClient(sqlite_manager=sqlite_manager)

    # Cache Manager
    cache_manager = CacheManager(
        sqlite_manager=sqlite_manager,
        ai_client=ai_client,
    )

    # Collectors
    github_collector = GitHubCollector(sqlite_manager=sqlite_manager)
    chrome_collector = ChromeCollector(sqlite_manager=sqlite_manager)
    gmail_collector = GmailCollector(sqlite_manager=sqlite_manager)
    gcal_collector = GCalCollector(sqlite_manager=sqlite_manager)
    filesystem_collector = FilesystemCollector(sqlite_manager=sqlite_manager)

    # Processors
    session_grouper = SessionGrouper(sqlite_manager=sqlite_manager)
    daily_processor = DailyProcessor(
        sqlite_manager=sqlite_manager,
        graph_manager=graph_manager,
        ai_client=ai_client,
        obsidian_writer=obsidian_writer,
        cache_manager=cache_manager,
    )
    weekly_synthesizer = WeeklySynthesizer(
        sqlite_manager=sqlite_manager,
        graph_manager=graph_manager,
        ai_client=ai_client,
        obsidian_writer=obsidian_writer,
    )

    logger.info("All components initialized successfully.")

    return {
        "sqlite_manager": sqlite_manager,
        "graph_manager": graph_manager,
        "obsidian_writer": obsidian_writer,
        "ai_client": ai_client,
        "cache_manager": cache_manager,
        "collectors": {
            "github": github_collector,
            "chrome": chrome_collector,
            "gmail": gmail_collector,
            "gcal": gcal_collector,
            "filesystem": filesystem_collector,
        },
        "processors": {
            "session_grouper": session_grouper,
            "daily_processor": daily_processor,
            "weekly_synthesizer": weekly_synthesizer,
        },
    }


def initialize_databases(sqlite_manager, graph_manager):
    """Initialize database schemas."""
    logger.info("Initializing databases...")
    sqlite_manager.initialize_db()
    graph_manager.initialize_db()
    logger.info("Databases initialized successfully.")


def start_filesystem_watcher(filesystem_collector):
    """Start the filesystem collector in a background daemon thread."""
    logger.info("Starting filesystem watcher in background thread...")
    watcher_thread = threading.Thread(
        target=filesystem_collector.collect,
        name="FilesystemWatcher",
        daemon=True,
    )
    watcher_thread.start()
    logger.info("Filesystem watcher started.")
    return watcher_thread


def setup_scheduler(task_runner):
    """Configure and return the APScheduler with all scheduled jobs."""
    scheduler = BlockingScheduler()

    processing_interval = settings.processing_interval_hours

    # Hourly: run all collectors (github, chrome, gmail, gcal)
    scheduler.add_job(
        task_runner.run_collectors,
        trigger=IntervalTrigger(hours=1),
        id="run_collectors",
        name="Run all data collectors",
        misfire_grace_time=300,
    )

    # Hourly: run session grouper
    scheduler.add_job(
        task_runner.run_session_grouping,
        trigger=IntervalTrigger(hours=1),
        id="run_session_grouping",
        name="Group activities into sessions",
        misfire_grace_time=300,
    )

    # Every PROCESSING_INTERVAL_HOURS: run daily processor
    scheduler.add_job(
        task_runner.run_daily_processing,
        trigger=IntervalTrigger(hours=processing_interval),
        id="run_daily_processing",
        name="Process daily activity summaries",
        misfire_grace_time=600,
    )

    # Weekly on Sunday at 20:00: run weekly synthesizer
    scheduler.add_job(
        task_runner.run_weekly_synthesis,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="run_weekly_synthesis",
        name="Synthesize weekly activity report",
        misfire_grace_time=3600,
    )

    # Daily at midnight: cleanup expired cache
    scheduler.add_job(
        task_runner.run_cache_cleanup,
        trigger=CronTrigger(hour=0, minute=0),
        id="run_cache_cleanup",
        name="Clean up expired cache entries",
        misfire_grace_time=600,
    )

    logger.info(
        "Scheduler configured with %d jobs.", len(scheduler.get_jobs())
    )
    return scheduler


def main():
    """Main entry point for the Personal Activity Intelligence System."""
    logger.info("=" * 60)
    logger.info("Personal Activity Intelligence System starting up...")
    logger.info("=" * 60)

    # Create all components
    components = create_components()

    # Initialize databases
    initialize_databases(
        components["sqlite_manager"],
        components["graph_manager"],
    )

    # Create task runner
    task_runner = TaskRunner(
        collectors=components["collectors"],
        session_grouper=components["processors"]["session_grouper"],
        daily_processor=components["processors"]["daily_processor"],
        weekly_synthesizer=components["processors"]["weekly_synthesizer"],
        cache_manager=components["cache_manager"],
    )

    # Start filesystem watcher in background
    start_filesystem_watcher(components["collectors"]["filesystem"])

    # Run collectors once at startup
    logger.info("Running initial data collection...")
    task_runner.run_collectors()

    # Set up the scheduler
    scheduler = setup_scheduler(task_runner)

    # Graceful shutdown handler
    def handle_shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("Received %s signal. Shutting down gracefully...", sig_name)
        scheduler.shutdown(wait=False)

        try:
            components["graph_manager"].close()
            logger.info("Graph database connection closed.")
        except Exception as e:
            logger.error("Error closing graph database: %s", e)

        logger.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start the scheduler (blocking)
    logger.info("Starting scheduler. System is now running.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("System interrupted. Exiting.")


if __name__ == "__main__":
    main()
