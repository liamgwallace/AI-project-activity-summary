"""
Main entry point for the Personal Activity Intelligence System.
Manages scheduling, data collection, and processing.
"""

import asyncio
import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from api.server import app
from collectors.calendar_collector import CalendarCollector
from collectors.gmail_collector import GmailCollector
from collectors.github_collector import GitHubCollector
from config.settings import get_settings, load_settings, Project, save_project
from processing.ai_processor import AIProcessor, ProcessingResult
from processing.batch_manager import BatchManager
from processing.project_detector import ProjectDetector
from storage.database import Database, Activity
from storage.obsidian_writer import ObsidianWriter

# Global components for graceful shutdown
db: Optional[Database] = None
scheduler: Optional[BackgroundScheduler] = None
obsidian_writer: Optional[ObsidianWriter] = None
shutdown_event = threading.Event()


def setup_logging() -> None:
    """Set up logging for the main application."""
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Main application log
    log_file = log_dir / "app.log"

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()

    # Stop the scheduler
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    sys.exit(0)


def run_collectors() -> None:
    """
    Run all data collectors and store events in the database.
    Collects from GitHub, Gmail, and Calendar.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting data collection cycle...")

    global db
    if not db:
        db = Database(get_settings().database.path)

    settings = get_settings()
    all_events: List[Dict[str, Any]] = []

    # Determine collection window (last hour)
    since = datetime.now() - timedelta(hours=1)

    # GitHub Collector
    if settings.github.token:
        try:
            logger.info("Collecting GitHub data...")
            github_collector = GitHubCollector(
                token=settings.github.token,
                username=settings.github.username,
            )
            github_events = github_collector.collect(since=since)
            all_events.extend(github_events)
            logger.info(f"GitHub: collected {len(github_events)} events")
        except Exception as e:
            logger.error(f"GitHub collection failed: {e}")
    else:
        logger.warning("GitHub token not configured, skipping GitHub collection")

    # Gmail Collector
    if settings.gmail.credentials_path and Path(settings.gmail.credentials_path).exists():
        try:
            logger.info("Collecting Gmail data...")
            gmail_collector = GmailCollector(
                credentials_path=settings.gmail.credentials_path,
            )
            gmail_events = gmail_collector.collect(since=since)
            all_events.extend(gmail_events)
            logger.info(f"Gmail: collected {len(gmail_events)} events")
        except Exception as e:
            logger.error(f"Gmail collection failed: {e}")
    else:
        logger.warning("Gmail credentials not configured, skipping Gmail collection")

    # Calendar Collector
    if settings.calendar.credentials_path and Path(settings.calendar.credentials_path).exists():
        try:
            logger.info("Collecting Calendar data...")
            calendar_collector = CalendarCollector(
                credentials_path=settings.calendar.credentials_path,
            )
            calendar_events = calendar_collector.collect(since=since)
            all_events.extend(calendar_events)
            logger.info(f"Calendar: collected {len(calendar_events)} events")
        except Exception as e:
            logger.error(f"Calendar collection failed: {e}")
    else:
        logger.warning("Calendar credentials not configured, skipping Calendar collection")

    # Store events in database
    if all_events:
        try:
            events_to_insert: List[tuple] = []
            for event in all_events:
                events_to_insert.append((
                    event.get("source", "unknown"),
                    event.get("event_type", "unknown"),
                    json.dumps(event.get("data", {})),
                    event.get("timestamp", datetime.now().isoformat()),
                ))

            inserted = db.insert_events(events_to_insert)
            logger.info(f"Stored {inserted} events in database")
        except Exception as e:
            logger.error(f"Failed to store events: {e}")
    else:
        logger.info("No events collected in this cycle")


def check_and_process() -> None:
    """
    Check if batch processing is needed and run AI processing if thresholds are met.
    Writes processed outputs to Obsidian vaults.
    """
    logger = logging.getLogger(__name__)
    logger.info("Checking if processing is needed...")

    global db, obsidian_writer
    if not db:
        db = Database(get_settings().database.path)
    if not obsidian_writer:
        settings = get_settings()
        project_vault = settings.obsidian.project_vault or str(Path(settings.data_dir) / "project-vault")
        personal_vault = settings.obsidian.personal_vault or str(Path(settings.data_dir) / "personal-vault")
        obsidian_writer = ObsidianWriter(
            project_vault=str(project_vault),
            personal_vault=str(personal_vault),
        )

    # Initialize batch manager
    batch_manager = BatchManager(db=db)

    # Check if processing should run
    if not batch_manager.should_process():
        logger.info("Processing not needed at this time")
        return

    logger.info("Processing threshold met, starting AI processing...")

    try:
        # Get events for processing
        events = batch_manager.get_events_for_batch()
        if not events:
            logger.info("No events to process")
            return

        # Get existing projects for context
        settings = get_settings()
        existing_projects: Dict[str, Dict[str, Any]] = {}
        for name, project in settings.projects.items():
            existing_projects[name] = {
                "description": project.description,
                "keywords": project.keywords,
                "tags": project.tags,
            }

        # Run AI processing
        processor = AIProcessor()
        result: ProcessingResult = processor.process_batch(events, existing_projects)

        if not result.success:
            logger.error(f"Processing failed: {result.error_message}")
            db.fail_batch(
                batch_id=db.create_batch(len(events), processor.model_config.get("model", "unknown")),
                error_message=result.error_message or "Unknown error",
            )
            return

        # Record the batch
        batch_id = db.create_batch(
            total_events=len(events),
            model_used=processor.model_config.get("model", "unknown"),
        )
        db.complete_batch(
            batch_id=batch_id,
            processed_count=len(result.activities),
            tokens_used=result.input_tokens + result.output_tokens,
        )

        # Mark events as processed
        event_ids = [e.id for e in events if e.id]
        db.mark_events_processed(event_ids)

        logger.info(
            f"Processed {len(events)} events into "
            f"{len(result.activities)} activities, "
            f"{len(result.new_projects)} new projects, "
            f"{len(result.tweets)} tweets"
        )

        # Handle new projects
        if result.new_projects:
            project_detector = ProjectDetector(db=db)
            approved_projects = project_detector.get_conservative_recommendations(
                result.new_projects,
                {},  # No pre-existing activities for new projects
            )

            for project_data in approved_projects:
                project_name = project_data.get("name", "")
                if project_name:
                    # Create and save the project
                    project = Project(
                        name=project_name,
                        description=project_data.get("description", ""),
                        tags=project_data.get("tags", []),
                        keywords=project_data.get("keywords", project_detector.get_project_keywords(
                            project_name, []
                        )),
                        active=True,
                        created_at=datetime.now().isoformat(),
                    )
                    save_project(project)
                    logger.info(f"Created new project: {project_name}")

        # Store activities and write to Obsidian
        activities_by_project: Dict[str, List[Activity]] = {}
        personal_activities: List[Dict[str, Any]] = []
        all_tweets: List[Dict[str, Any]] = []

        for activity_data in result.activities:
            project_name = activity_data.get("project", activity_data.get("project_name", "misc"))
            
            # Insert into database
            activity_id = db.insert_activity(
                timestamp=activity_data.get("timestamp", datetime.now().isoformat()),
                project_name=project_name,
                activity_type=activity_data.get("type", activity_data.get("activity_type", "activity")),
                description=activity_data.get("description", ""),
                source_refs=json.dumps(activity_data.get("sources", [])),
                raw_event_ids=json.dumps([e.id for e in events if e.id]),
            )

            activity_dict = {
                "id": activity_id,
                "date": activity_data.get("timestamp", "")[:10],
                "description": activity_data.get("description", ""),
                "type": activity_data.get("type", activity_data.get("activity_type", "activity")),
                "technologies": activity_data.get("technologies", []),
                "project": project_name,
            }

            if project_name == "misc" or not project_name:
                personal_activities.append(activity_dict)
            else:
                if project_name not in activities_by_project:
                    activities_by_project[project_name] = []
                activities_by_project[project_name].append(activity_dict)

        # Store tweet drafts
        for tweet_data in result.tweets:
            draft_id = db.insert_tweet_draft(
                content=tweet_data.get("content", tweet_data.get("tweet", "")),
                project_name=tweet_data.get("project", tweet_data.get("project_name", "unknown")),
                activity_ids=json.dumps(tweet_data.get("activity_ids", [])),
                timestamp=tweet_data.get("timestamp", datetime.now().isoformat()),
            )
            all_tweets.append({
                "id": draft_id,
                **tweet_data,
            })

        # Write to Obsidian
        try:
            # Write project activity logs
            for project_name, activities in activities_by_project.items():
                obsidian_writer.write_activity_log(project_name, activities)
                logger.info(f"Wrote activity log for {project_name}")

            # Write personal activities
            if personal_activities:
                obsidian_writer.write_personal_activity_log(personal_activities)
                logger.info(f"Wrote personal activity log ({len(personal_activities)} activities)")

            # Write tweet drafts
            if all_tweets:
                obsidian_writer.write_tweet_drafts(all_tweets)
                logger.info(f"Wrote {len(all_tweets)} tweet drafts")

        except Exception as e:
            logger.error(f"Error writing to Obsidian: {e}")

    except Exception as e:
        logger.error(f"Error during processing: {e}")


def run_weekly_synthesis() -> None:
    """
    Run weekly synthesis to update README files with weekly summaries.
    Generates summaries via AIProcessor and updates via ObsidianWriter.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting weekly synthesis...")

    global db, obsidian_writer
    if not db:
        db = Database(get_settings().database.path)
    if not obsidian_writer:
        settings = get_settings()
        project_vault = settings.obsidian.project_vault or str(Path(settings.data_dir) / "project-vault")
        personal_vault = settings.obsidian.personal_vault or str(Path(settings.data_dir) / "personal-vault")
        obsidian_writer = ObsidianWriter(
            project_vault=str(project_vault),
            personal_vault=str(personal_vault),
        )

    try:
        # Get activities from last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        settings = get_settings()
        processor = AIProcessor()

        # Process each active project
        for project_name in settings.projects.keys():
            # Get activities for this project
            activities = db.get_activities_for_period(
                start=start_date,
                end=end_date,
                project_name=project_name,
            )

            if not activities:
                logger.debug(f"No activities for {project_name} this week")
                continue

            # Read current README if exists
            project_folder = obsidian_writer.ensure_project_folder(project_name)
            readme_file = project_folder / "README.md"
            current_readme = ""
            if readme_file.exists():
                current_readme = readme_file.read_text(encoding="utf-8")

            # Generate weekly summary
            weekly_summary = processor.weekly_synthesis(
                project_name=project_name,
                activities=activities,
                current_readme=current_readme,
            )

            # Update README
            obsidian_writer.update_project_readme(project_name, weekly_summary)
            logger.info(f"Updated README for {project_name} with weekly summary")

        logger.info("Weekly synthesis completed")

    except Exception as e:
        logger.error(f"Error during weekly synthesis: {e}")


def setup_scheduler() -> BackgroundScheduler:
    """
    Configure and start the APScheduler with all jobs.

    Schedule:
    - Every hour: run_collectors()
    - Every hour: check_and_process() (only if thresholds met)
    - Sunday 20:00: run_weekly_synthesis()

    Returns:
        Configured BackgroundScheduler instance
    """
    logger = logging.getLogger(__name__)
    logger.info("Setting up scheduler...")

    scheduler = BackgroundScheduler()

    # Run collectors every hour
    scheduler.add_job(
        run_collectors,
        trigger=IntervalTrigger(hours=1),
        id="collectors",
        name="Data Collection",
        replace_existing=True,
    )
    logger.info("Scheduled: run_collectors() every hour")

    # Check and process every hour
    scheduler.add_job(
        check_and_process,
        trigger=IntervalTrigger(hours=1),
        id="processor",
        name="Batch Processing",
        replace_existing=True,
    )
    logger.info("Scheduled: check_and_process() every hour")

    # Weekly synthesis on Sundays at 20:00
    scheduler.add_job(
        run_weekly_synthesis,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="weekly_synthesis",
        name="Weekly Synthesis",
        replace_existing=True,
    )
    logger.info("Scheduled: run_weekly_synthesis() Sundays at 20:00")

    return scheduler


def run_api_server() -> None:
    """Run the FastAPI server using uvicorn."""
    logger = logging.getLogger(__name__)
    logger.info("Starting FastAPI server...")

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
    except Exception as e:
        logger.error(f"API server error: {e}")


def main() -> None:
    """Main entry point. Starts scheduler and API server."""
    # Load settings
    load_settings()
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Personal Activity Intelligence System Starting")
    logger.info("=" * 60)

    # Initialize global components
    global db, scheduler, obsidian_writer
    settings = get_settings()
    
    db = Database(settings.database.path)
    project_vault = settings.obsidian.project_vault or str(Path(settings.data_dir) / "project-vault")
    personal_vault = settings.obsidian.personal_vault or str(Path(settings.data_dir) / "personal-vault")
    obsidian_writer = ObsidianWriter(
        project_vault=str(project_vault),
        personal_vault=str(personal_vault),
    )

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set up and start scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # Start the API server in the main thread
    # Note: Using threading for scheduler + main thread for API server
    logger.info("Starting API server on http://localhost:8000")
    
    try:
        # Run the API server (blocking call)
        run_api_server()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        # Clean shutdown
        signal_handler(0, None)


if __name__ == "__main__":
    main()
