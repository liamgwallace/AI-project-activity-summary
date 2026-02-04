# Personal Activity Intelligence System (PAIS)

A self-hosted system that collects personal activity data from GitHub, Gmail, Google Calendar, and browser history, processes it with AI, and outputs organized notes to Obsidian.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [CLI Commands](#cli-commands)
- [Chrome Extension](#chrome-extension)
- [Docker Deployment](#docker-deployment)
- [Obsidian Integration](#obsidian-integration)
- [Database Schema](#database-schema)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Overview

PAIS automatically tracks your digital activities and transforms them into organized, searchable notes. It connects to various services you use daily and uses AI to:

- **Group related activities** into coherent project work
- **Extract technologies and tools** used
- **Generate tweet drafts** for significant accomplishments
- **Create weekly summaries** of your work
- **Organize everything** in Obsidian vaults

### Data Sources

| Source | Data Collected | Collection Frequency |
|--------|---------------|---------------------|
| **GitHub** | Commits, Pull Requests, Issues | Hourly |
| **Gmail** | Emails (metadata only) | Hourly |
| **Google Calendar** | Events and meetings | Hourly |
| **Browser History** | Page visits via Chrome extension | Real-time |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA COLLECTION LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  GitHub  │  │  Gmail   │  │ Calendar │  │   Browser    │    │
│  │  API     │  │  API     │  │  API     │  │  Extension   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘    │
└───────┼─────────────┼─────────────┼───────────────┼────────────┘
        │             │             │               │
        └─────────────┴─────────────┴───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  Scheduler   │───▶│   AI Model   │───▶│  Batch Mgr   │     │
│  │  (Hourly)    │    │ (OpenRouter) │    │              │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   Weekly     │    │   Activity   │    │   Project    │     │
│  │   Synthesis  │    │   Analysis   │    │   Detection  │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT LAYER                                 │
│  ┌────────────────────┐    ┌────────────────────┐            │
│  │   Project Vault    │    │   Personal Vault   │            │
│  │   /project-vault/  │    │   /personal-vault/ │            │
│  │   ├── project-1/   │    │   ├── activity-log │            │
│  │   │   ├── README.md│    │   └── tweets/      │            │
│  │   │   └── activity │    │                    │            │
│  │   └── project-2/   │    │                    │            │
│  └────────────────────┘    └────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### Core Features

- **Multi-Source Collection**: Aggregate data from GitHub, Gmail, Google Calendar, and browser history
- **AI-Powered Processing**: Uses GPT-4o-mini via OpenRouter for intelligent activity analysis
- **Project Detection**: Automatically detects and manages projects based on activity patterns
- **Obsidian Integration**: Outputs organized Markdown files to Obsidian-compatible vaults
- **Weekly Synthesis**: Automatically generates weekly summaries every Sunday
- **Tweet Draft Generation**: Creates shareable tweet drafts for notable accomplishments

### Data Collection Features

- **Rate Limit Handling**: Respects API rate limits with automatic backoff
- **Offline Queue**: Chrome extension queues visits when offline
- **Incremental Sync**: Only fetches new data since last collection
- **Duplicate Detection**: Prevents duplicate event storage

### Processing Features

- **Batch Processing**: Groups events for efficient AI processing
- **Technology Extraction**: Automatically identifies tools and technologies used
- **Conservative Project Creation**: Only creates new projects for substantial work
- **Token Usage Tracking**: Monitors and reports API usage and costs

## Quick Start

Get PAIS running in under 5 minutes:

```bash
# 1. Clone the repository
git clone <repository-url>
cd AI-project-activity-summary

# 2. Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Run with Docker (recommended)
docker-compose up -d

# 4. Test the installation
python -m cli.commands test-db
```

Access the API at `http://localhost:8000` and view health status at `http://localhost:8000/api/health`.

## Installation

### Prerequisites

- **Python 3.12** or higher
- **Docker** and **Docker Compose** (optional but recommended)
- **GitHub Account** with personal access token
- **Google Account** for Gmail/Calendar access
- **OpenRouter or OpenAI Account** with API key
- **Chrome Browser** for browser history tracking

### Step-by-Step Installation

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd AI-project-activity-summary
```

#### 2. Install Dependencies

**Option A: Using pip (local development)**

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Option B: Using Docker (production)**

```bash
# Build the image
docker-compose build

# Start the services
docker-compose up -d
```

#### 3. Environment Setup

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

#### 4. Google OAuth Setup

For Gmail and Calendar access, you need to set up OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs:
   - Gmail API
   - Google Calendar API
4. Create OAuth 2.0 credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth client ID"
   - Select "Desktop app" as application type
   - Download the JSON credentials files
5. Place the downloaded files:
   - `config/gmail_credentials.json` (for Gmail)
   - `config/calendar_credentials.json` (for Calendar)

**First Run Authentication:**

The first time you run the collectors, a browser window will open for OAuth authentication. The tokens will be saved automatically.

#### 5. GitHub Token Setup

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token with these scopes:
   - `repo` - Access repositories
   - `read:user` - Read user profile data
   - `read:org` - Read organization data (optional)
3. Copy the token to your `.env` file:
   ```
   PAIS_GITHUB_TOKEN=ghp_your_token_here
   PAIS_GITHUB_USERNAME=your_username
   ```

#### 6. OpenRouter/OpenAI Setup

**Option A: OpenRouter (Recommended)**

1. Create an account at [OpenRouter](https://openrouter.ai/)
2. Generate an API key
3. Add to `.env`:
   ```
   PAIS_OPENAI_API_KEY=sk-or-v1-your_key
   ```
   
   The system will automatically detect OpenRouter by the API key format.

**Option B: OpenAI**

1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `.env`:
   ```
   PAIS_OPENAI_API_KEY=sk-your_key
   PAIS_OPENAI_MODEL=gpt-4o-mini
   ```

## Configuration

### Environment Variables

All configuration is done via environment variables. Create a `.env` file:

```bash
# Application Settings
PAIS_DEBUG=false
PAIS_DATA_DIR=data
PAIS_LOG_DIR=logs
PAIS_CONFIG_DIR=config

# Database
PAIS_DB_PATH=data/activity_system.db

# GitHub Integration
PAIS_GITHUB_TOKEN=ghp_your_token
PAIS_GITHUB_USERNAME=your_username
PAIS_GITHUB_REPOS=owner/repo1,owner/repo2  # Optional: limit to specific repos
PAIS_GITHUB_FETCH_COMMITS=true
PAIS_GITHUB_FETCH_PRS=true
PAIS_GITHUB_FETCH_ISSUES=true
PAIS_GITHUB_FETCH_REVIEWS=true

# Gmail Integration
PAIS_GMAIL_CREDENTIALS_PATH=config/gmail_credentials.json
PAIS_GMAIL_TOKEN_PATH=data/gmail_token.json
PAIS_GMAIL_QUERY_DAYS=7
PAIS_GMAIL_LABELS=INBOX,SENT

# Google Calendar Integration
PAIS_CALENDAR_CREDENTIALS_PATH=config/calendar_credentials.json
PAIS_CALENDAR_TOKEN_PATH=data/calendar_token.json
PAIS_CALENDAR_CALENDARS=primary,work,personal

# AI Configuration (OpenRouter or OpenAI)
PAIS_OPENAI_API_KEY=sk-your_key
PAIS_OPENAI_MODEL=gpt-4o-mini
PAIS_OPENAI_TEMPERATURE=0.3
PAIS_OPENAI_MAX_TOKENS=2000
PAIS_OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Server Configuration
PAIS_HOST=0.0.0.0
PAIS_PORT=8000
PAIS_WORKERS=1

# Security
PAIS_SECRET_KEY=your-secret-key-here-change-in-production
PAIS_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Projects Configuration

Projects can be configured in `config/projects.json`:

```json
{
  "my-project": {
    "description": "My awesome project",
    "tags": ["python", "web"],
    "keywords": ["fastapi", "api"],
    "active": true,
    "created_at": "2024-01-01T00:00:00"
  }
}
```

## Usage

### Starting the System

**Local development:**

```bash
python main.py
```

This starts:
- Background scheduler (hourly collection + processing)
- FastAPI server on port 8000

**Docker:**

```bash
docker-compose up -d
docker-compose logs -f
```

### Running Collectors Manually

```bash
# Test individual collectors
python -m cli.commands test-github
python -m cli.commands test-gmail
python -m cli.commands test-calendar

# Collect from all sources
python -m cli.commands collect-all

# Collect with skips
python -m cli.commands collect-all --skip-gmail --skip-calendar
```

### Processing Data

```bash
# Process unprocessed events immediately
python -m cli.commands process-now

# Process with limit
python -m cli.commands process-now --limit 50
```

### Viewing Results

```bash
# Show recent events
python -m cli.commands show-events --days 7 --limit 20

# Show with full data
python -m cli.commands show-events --verbose

# Show system statistics
python -m cli.commands show-stats --days 30

# Generate activity logs
python -m cli.commands generate-logs --days 7 --output logs/activity.json
```

## CLI Commands

The CLI provides commands for testing, collecting, processing, and managing the system.

### Testing Commands

| Command | Description | Options |
|---------|-------------|---------|
| `test-github` | Test GitHub API connection | `--store` - Store results |
| `test-gmail` | Test Gmail API connection | None |
| `test-calendar` | Test Calendar API connection | None |
| `test-db` | Test database operations | None |
| `test-ai` | Test AI model connectivity | None |

### Data Collection Commands

| Command | Description | Options |
|---------|-------------|---------|
| `collect-all` | Collect from all sources | `--skip-github`, `--skip-gmail`, `--skip-calendar` |

### Processing Commands

| Command | Description | Options |
|---------|-------------|---------|
| `process-now` | Process unprocessed events | `--limit N` - Max events to process |

### Reporting Commands

| Command | Description | Options |
|---------|-------------|---------|
| `show-events` | Display recent events | `--days N`, `--limit N`, `--verbose` |
| `show-stats` | Show system statistics | `--days N` |
| `generate-logs` | Generate activity logs | `--days N`, `--project NAME`, `--output FILE` |

### Usage Examples

```bash
# Test everything
python -m cli.commands test-db
python -m cli.commands test-github --store
python -m cli.commands test-gmail
python -m cli.commands test-calendar
python -m cli.commands test-ai

# Full collection cycle
python -m cli.commands collect-all
python -m cli.commands process-now

# Get weekly report
python -m cli.commands generate-logs --days 7 --output weekly-report.json
```

## Chrome Extension

The Chrome extension tracks your browsing activity and sends it to PAIS in real-time.

### Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome_extension` folder from this project
5. The extension icon should appear in your toolbar

### Configuration

1. Click the extension icon → "Options"
2. Configure these settings:
   - **API Endpoint**: `http://localhost:8000/api/browser/visit`
   - **API Key**: (optional) If you've set `PAIS_SECRET_KEY` in your `.env`
   - **Device Name**: e.g., "desktop", "laptop"

3. Click "Save Settings"
4. Click "Test Connection" to verify

### Features

- **Real-time tracking**: Sends page visits as you browse
- **Offline support**: Queues visits when offline, sends when reconnected
- **Privacy filtering**: Ignores `chrome://` and extension pages
- **Retry logic**: Automatically retries failed sends (max 5 attempts)

### Disabling Tracking

- Toggle the extension off in `chrome://extensions/`
- Or disable tracking in the options page

## Docker Deployment

### Basic Deployment

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment

```bash
# Build with no cache (clean build)
docker-compose build --no-cache

# Run in detached mode with restart policy
docker-compose up -d --restart unless-stopped

# View specific service logs
docker-compose logs -f pais
```

### Volume Persistence

The `docker-compose.yml` mounts these volumes:
- `./data:/app/data` - Database, vaults, and OAuth tokens (read-write)
- `./logs:/app/logs` - Application logs
- `./config:/app/config:ro` - Configuration and credentials (read-only)

**Note**: OAuth tokens are stored in `./data/` (not `./config/`) so they can be refreshed by the application while keeping credentials read-only.

### Container Entrypoint

The Docker container uses an entrypoint script (`docker/entrypoint.sh`) that validates your setup before starting the application:

- Checks for required credential files (`gmail_credentials.json`, `calendar_credentials.json`)
- Verifies OAuth token files exist or will be created
- Validates environment variables (GitHub token, OpenAI key)
- Ensures proper directory permissions
- Checks database initialization

You'll see validation output when the container starts:
```bash
docker-compose up
# Output shows:
# ✓ Creating required directories...
# ✓ gmail_credentials.json found
# ⚠ gmail_token.json not found - will be created on first Gmail auth
# ✓ PAIS_GITHUB_TOKEN is set
```

If credentials are missing, the container will start but warn you about disabled integrations.

### Health Checks

The container includes a health check that verifies the API is responding:

```bash
# Check health
curl http://localhost:8000/api/health

# Docker health status
docker-compose ps
```

### Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

## Obsidian Integration

PAIS creates two Obsidian vaults with organized Markdown files.

### Vault Structure

```
data/
├── project-vault/          # Project-specific notes
│   ├── my-project/
│   │   ├── README.md       # Weekly summaries and overview
│   │   └── activity-log.md # Detailed activity timeline
│   └── another-project/
│       ├── README.md
│       └── activity-log.md
│
└── personal-vault/         # Personal notes
    ├── personal-activity-log.md
    └── tweets/
        └── drafts.md       # Tweet drafts generated by AI
```

### File Format

**Activity Logs** (`activity-log.md`):
```markdown
---
project: "my-project"
created: "2024-01-15T10:30:00"
type: "activity-log"
---

# Activity Log: my-project

## 2024-01-15

- **[commit]** Refactored authentication module
  - Technologies: python, fastapi, jwt

- **[pr]** Merged feature branch for user profiles
  - Technologies: react, typescript
```

**README.md** (auto-updated weekly):
```markdown
---
project: "my-project"
created: "2024-01-01T00:00:00"
type: "readme"
---

# my-project

## Week of Jan 14, 2024

- Implemented user authentication system
- Set up CI/CD pipeline with GitHub Actions
- Created initial database schema

## Week of Jan 07, 2024

- Project initialization
- Defined core requirements
```

### Opening in Obsidian

1. Open Obsidian
2. Click "Open folder as vault"
3. Select either:
   - `data/project-vault` for project notes
   - `data/personal-vault` for personal notes
4. Or open the parent `data` folder to access both

### Recommended Obsidian Plugins

- **Dataview**: Query and display activities dynamically
- **Templater**: Create custom templates for new projects
- **Git**: Sync vaults to a git repository
- **Calendar**: Visualize activity patterns

## Database Schema

PAIS uses SQLite for data storage. The database file is located at `data/activity_system.db`.

### Tables

#### raw_events

Stores unprocessed events from all sources.

```sql
CREATE TABLE raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,           -- 'github', 'gmail', 'calendar', 'browser'
    event_type TEXT NOT NULL,       -- 'commit', 'pr', 'email', 'event', 'visit'
    raw_data TEXT NOT NULL,         -- JSON blob with event details
    event_time TEXT NOT NULL,       -- ISO timestamp
    processed INTEGER DEFAULT 0,   -- 0=unprocessed, 1=processed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### activities

Processed and categorized activities.

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    project_name TEXT NOT NULL,     -- 'my-project', 'misc'
    activity_type TEXT NOT NULL,    -- 'commit', 'email', 'meeting'
    description TEXT NOT NULL,
    source_refs TEXT,               -- JSON array of source references
    tweet_draft_id INTEGER,         -- FK to tweet_drafts
    raw_event_ids TEXT,             -- JSON array of raw_event IDs
    embedding BLOB,                 -- Vector embedding (future use)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### processing_batches

Tracks AI processing jobs.

```sql
CREATE TABLE processing_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_events INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    model_used TEXT,
    tokens_used INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### tweet_drafts

Generated tweet content.

```sql
CREATE TABLE tweet_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    project_name TEXT NOT NULL,
    activity_ids TEXT,              -- JSON array
    timestamp TEXT NOT NULL,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    posted INTEGER DEFAULT 0,      -- 0=draft, 1=posted
    posted_at TEXT,
    engagement_stats TEXT DEFAULT '{}' -- JSON with likes, retweets
);
```

#### projects

Project definitions and metadata.

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    keywords TEXT,                  -- Comma-separated
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### token_usage

Tracks AI API usage and costs.

```sql
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    operation TEXT NOT NULL,        -- 'daily_process', 'weekly_synthesis'
    model TEXT NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0.0
);
```

### Indexes

```sql
CREATE INDEX idx_raw_events_processed ON raw_events(processed);
CREATE INDEX idx_raw_events_time ON raw_events(event_time);
CREATE INDEX idx_activities_project ON activities(project_name);
CREATE INDEX idx_activities_time ON activities(timestamp);
```

### Accessing the Database

```bash
# Using SQLite CLI
sqlite3 data/activity_system.db

# Common queries
SELECT * FROM raw_events WHERE processed = 0;
SELECT project_name, COUNT(*) FROM activities GROUP BY project_name;
SELECT * FROM token_usage ORDER BY timestamp DESC LIMIT 10;
```

## Development

### Project Structure

```
AI-project-activity-summary/
├── api/                    # FastAPI server
│   ├── server.py          # Main API endpoints
│   └── __init__.py
├── chrome_extension/       # Browser extension
│   ├── background.js      # Service worker
│   ├── options.html/js    # Options page
│   ├── popup.html/js      # Popup UI
│   └── manifest.json
├── cli/                   # Command-line interface
│   ├── commands.py       # CLI commands
│   └── __init__.py
├── collectors/           # Data collection modules
│   ├── base.py          # Base collector class
│   ├── browser_receiver.py
│   ├── calendar_collector.py
│   ├── github_collector.py
│   └── gmail_collector.py
├── config/              # Configuration management
│   ├── settings.py     # Settings dataclasses
│   └── __init__.py
├── processing/          # AI processing modules
│   ├── ai_processor.py
│   ├── batch_manager.py
│   ├── project_detector.py
│   └── prompts/        # AI prompts
│       ├── daily_process.py
│       └── weekly_synthesis.py
├── storage/             # Data persistence
│   ├── database.py     # SQLite operations
│   └── obsidian_writer.py
├── docker-compose.yml
├── Dockerfile
├── main.py             # Application entry point
├── requirements.txt
└── .env.example
```

### Adding a New Collector

1. Create a new file in `collectors/`:

```python
# collectors/jira_collector.py
from datetime import datetime
from typing import List, Dict, Any
from collectors.base import BaseCollector

class JiraCollector(BaseCollector):
    def __init__(self, api_token: str, domain: str):
        super().__init__("jira")
        self.api_token = api_token
        self.domain = domain
    
    def collect(self, since: datetime) -> List[Dict[str, Any]]:
        # Implementation
        pass
```

2. Add configuration in `config/settings.py`:

```python
@dataclass
class JiraConfig:
    api_token: str = ""
    domain: str = ""
```

3. Register in `main.py`:

```python
from collectors.jira_collector import JiraCollector

# In run_collectors():
if settings.jira.api_token:
    jira_collector = JiraCollector(...)
    events = jira_collector.collect(since)
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with coverage
pytest --cov=.
```

### Code Style

This project follows PEP 8. Use `black` and `isort` for formatting:

```bash
# Install formatters
pip install black isort

# Format code
black .
isort .
```

## Troubleshooting

### Common Issues

#### GitHub Rate Limit Exceeded

**Problem**: `Error: API rate limit exceeded`

**Solution**: 
- The system automatically handles rate limits with backoff
- For large repositories, consider using a GitHub App instead of personal token
- Check remaining rate limit: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

#### Gmail OAuth Expired

**Problem**: `Token has been expired or revoked`

**Solution**:
1. Delete the token file: `rm data/gmail_token.json`
2. Run the collector again: `python -m cli.commands test-gmail`
3. Re-authenticate in the browser window

#### AI Processing Fails

**Problem**: `Error: Failed to process batch`

**Solution**:
- Check API key is valid: `python -m cli.commands test-ai`
- Verify network connectivity
- Check OpenRouter/OpenAI status page
- Review logs in `logs/app.log`

#### Database Locked

**Problem**: `sqlite3.OperationalError: database is locked`

**Solution**:
- Only one process should access the database at a time
- If using Docker, ensure container is not being accessed from host simultaneously
- Restart the application

#### Chrome Extension Not Sending Data

**Problem**: No browser visits appearing

**Solution**:
1. Check extension is enabled: `chrome://extensions/`
2. Verify API endpoint is correct in options
3. Test connection from options page
4. Check browser console for errors (F12 → Console)
5. Verify API server is running: `curl http://localhost:8000/api/health`

### Logs and Debugging

```bash
# View application logs
tail -f logs/app.log

# Enable debug mode
PAIS_DEBUG=true python main.py

# View Docker logs
docker-compose logs -f pais
```

### Resetting the System

```bash
# Clear database (WARNING: destroys all data)
rm data/activity_system.db

# Clear processed flags (reprocess everything)
sqlite3 data/activity_system.db "UPDATE raw_events SET processed = 0;"

# Clear Obsidian vaults
rm -rf data/project-vault/* data/personal-vault/*

# Reset OAuth tokens
rm data/gmail_token.json data/calendar_token.json
```

### Getting Help

1. Check the logs: `logs/app.log`
2. Run diagnostics: `python -m cli.commands test-db`
3. Verify configuration: Review `.env` file
4. Check API status:
   - GitHub: https://www.githubstatus.com/
   - OpenAI: https://status.openai.com/
   - OpenRouter: https://status.openrouter.ai/

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI processing powered by [OpenRouter](https://openrouter.ai/) or [OpenAI](https://openai.com/)
- Data collection via [PyGithub](https://github.com/PyGithub/PyGithub) and Google APIs
- Task scheduling with [APScheduler](https://apscheduler.readthedocs.io/)
