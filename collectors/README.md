# Collectors Module

Data collectors for gathering activity from external sources.

## Description

The collectors module fetches activity data from GitHub, Gmail, Google Calendar, and browser history. Each collector implements a common interface and converts source-specific data into standardized event format.

## Files

- `base.py` - Abstract base class defining the collector interface
- `github_collector.py` - GitHub commits and pull requests
- `gmail_collector.py` - Gmail emails and threads
- `calendar_collector.py` - Google Calendar events
- `browser_receiver.py` - Browser page visits (received via API)
- `__init__.py` - Package initialization

## Key Classes

### BaseCollector (Abstract)
Base class for all collectors:
- `__init__(source_name)` - Initialize with logging setup
- `collect(since: datetime)` - Fetch events since date (abstract)
- `test()` - Test collector with sample data (abstract)
- `_create_event()` - Create standardized event dictionary

### GitHubCollector
Collects GitHub activity:
- `__init__(token, username)` - Initialize with PyGithub client
- `collect(since)` - Fetch commits and PRs from accessible repos
- `_check_rate_limit()` - Rate limit handling with wait logic
- `_fetch_commits(repo, since)` - Get commits by user
- `_fetch_prs(repo, since)` - Get pull requests by user

### GmailCollector
Collects Gmail activity:
- `__init__(credentials_path)` - Initialize with OAuth credentials
- `_get_service()` - OAuth flow and token management
- `collect(since)` - Query emails from configured labels
- `_parse_email(message)` - Extract headers and metadata

### CalendarCollector
Collects calendar events:
- `__init__(credentials_path)` - Initialize with OAuth credentials
- `_get_service()` - OAuth flow for Calendar API
- `collect(since)` - Query events from primary calendar
- `_parse_event(event)` - Parse event into standardized format

### BrowserReceiver
Receives browser activity:
- `receive_page_visit(url, title, timestamp, device, api_key)` - Store page visit
- `collect(since)` - Query stored browser events from database
- `test()` - Record and verify a sample event

## Event Format

All collectors produce standardized events:
```python
{
    "timestamp": "ISO datetime",
    "source": "github|gmail|calendar|browser",
    "event_type": "commit|pr|email|calendar_event|page_visit",
    "data": { ... }  # Source-specific data
}
```

## Usage

```python
from collectors.github_collector import GitHubCollector
from datetime import datetime, timedelta

collector = GitHubCollector(token="ghp_xxx", username="user")
events = collector.collect(since=datetime.now() - timedelta(days=1))
```

## Dependencies

- `PyGithub` - GitHub API client
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` - Google APIs
