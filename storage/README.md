# Storage Module

SQLite database operations and Obsidian vault output writer.

## Description

The storage module handles all data persistence including raw event storage, activity records, and Obsidian vault markdown generation. Provides dataclasses for type-safe database operations.

## Files

- `database.py` - SQLite database manager with CRUD operations
- `obsidian_writer.py` - Obsidian vault markdown writer
- `__init__.py` - Package initialization

## Key Classes

### Database
SQLite database manager:
- `__init__(db_path)` - Initialize and create tables
- `_get_connection()` - Get connection with row factory
- `_init_tables()` - Create all tables and indexes

### Data Models (Dataclasses)
- `RawEvent` - id, source, event_type, raw_data, event_time, processed, created_at
- `ProcessingBatch` - id, start_time, end_time, total_events, processed_count, status
- `Activity` - id, timestamp, project_name, activity_type, description, source_refs
- `TweetDraft` - id, content, project_name, activity_ids, timestamp, posted

### CRUD Operations

**Raw Events:**
- `insert_event(source, event_type, raw_data, event_time)` - Insert single event
- `insert_events(events)` - Batch insert
- `get_unprocessed_events(limit)` - Fetch pending events
- `get_events_since(since)` - Query events by date
- `mark_events_processed(event_ids)` - Mark events as processed

**Processing Batches:**
- `create_batch(total_events, model_used)` - Start new batch
- `complete_batch(batch_id, processed_count, tokens_used)` - Finish batch
- `fail_batch(batch_id, error_message)` - Mark batch failed

**Activities:**
- `insert_activity(timestamp, project_name, activity_type, description, ...)` - Create activity
- `get_activities_for_period(start, end, project_name)` - Query by date range

**Projects:**
- `get_or_create_project(name, description, keywords)` - Get or create project

**Token Usage:**
- `record_token_usage(operation, model, tokens_input, tokens_output, cost_estimate)` - Log usage
- `get_token_stats(days)` - Get statistics for period

**Tweet Drafts:**
- `insert_tweet_draft(content, project_name, activity_ids, timestamp)` - Create draft

### ObsidianWriter
Markdown file generator:
- `__init__(project_vault, personal_vault)` - Initialize with vault paths
- `ensure_project_folder(project_name)` - Create project directory (kebab-case)
- `write_activity_log(project_name, activities)` - Generate activity-log.md
- `write_personal_activity_log(activities)` - Generate personal-activity-log.md
- `update_project_readme(project_name, weekly_summary)` - Prepend weekly section
- `write_tweet_drafts(tweets)` - Write to tweets/drafts.md

**Features:**
- YAML frontmatter generation
- Date-grouped activity logs
- Weekly README section insertion
- Kebab-case folder naming
- Automatic directory creation

## Database Schema

Tables created automatically:
- `raw_events` - Incoming events from collectors
- `processing_batches` - Batch processing tracking
- `activities` - Processed and categorized activities
- `tweet_drafts` - Generated social media content
- `projects` - Project definitions and keywords
- `token_usage` - AI token consumption tracking

Indexes:
- `idx_raw_events_processed` - Fast unprocessed queries
- `idx_raw_events_time` - Time-based queries
- `idx_activities_project` - Project filtering
- `idx_activities_time` - Date range queries

## Usage

```python
from storage.database import Database
from storage.obsidian_writer import ObsidianWriter

# Database operations
db = Database("data/activity_system.db")
event_id = db.insert_event("github", "commit", json_data, timestamp)
unprocessed = db.get_unprocessed_events(limit=100)

# Obsidian output
writer = ObsidianWriter("vault/projects", "vault/personal")
writer.write_activity_log("my-project", activities)
writer.update_project_readme("my-project", weekly_summary)
```

## Dependencies

- Standard library: `sqlite3`, `json`, `dataclasses`, `pathlib`
