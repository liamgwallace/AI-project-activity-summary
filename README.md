# Personal Activity Intelligence System

A self-hosted system that collects personal activity data from multiple sources (GitHub, filesystem, browser, calendar, email), processes it with AI to detect projects and themes, and outputs organized notes to Obsidian with optional tweet generation.

## Architecture

```
Collectors (hourly) → SQLite staging → Session Grouper → AI Processing → Neo4j graph + Obsidian output
                                                                          ↓
                                                         Weekly Synthesis → README updates
```

### Data Flow

1. **Hourly Collection**: Collectors grab raw data from GitHub, Chrome, Gmail, Google Calendar, and the local filesystem
2. **Session Grouping**: Events grouped by temporal proximity (configurable gap, default 1 hour)
3. **AI Processing**: Sessions sent to AI (via LangChain + OpenRouter) on a scheduled interval (default 6 hours)
4. **Graph Storage**: Extracted entities and relationships stored in Neo4j
5. **Obsidian Output**: Activity logs (last 7 days) written as human-readable markdown
6. **Weekly Synthesis**: Deeper AI review updates project README files every Sunday

## Data Sources

| Source | Collector | What's Collected |
|--------|-----------|-----------------|
| GitHub | `collectors/github_collector.py` | Commits, PRs, repository activity |
| Filesystem | `collectors/filesystem_collector.py` | File creates/edits/deletes in monitored dirs |
| Chrome | `collectors/chrome_collector.py` | URLs visited, page titles (via Chrome Sync OAuth) |
| Gmail | `collectors/gmail_collector.py` | Email subjects, senders, content snippets |
| Google Calendar | `collectors/gcal_collector.py` | Event titles, times, descriptions |

## AI Models (via OpenRouter)

| Task | Model | Purpose |
|------|-------|---------|
| Summarization | Claude Haiku | Cheap webpage summarization |
| Daily Processing | Claude Sonnet | Extract events, classify to projects |
| Weekly Synthesis | Claude Sonnet | Deep analysis and README updates |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- GitHub token
- Google OAuth credentials (for Chrome, Gmail, Calendar)
- OpenRouter API key

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your credentials
3. Configure `config/monitored_paths.json` with your filesystem paths
4. Run with Docker Compose:

```bash
docker-compose up -d
```

### Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_GAP_MINUTES` | 60 | Inactivity gap to split sessions |
| `PROCESSING_INTERVAL_HOURS` | 6 | How often to run AI processing |
| `MAX_CONTEXT_CHARS` | 50000 | Max chars per AI processing batch |
| `OBSIDIAN_PROJECT_VAULT_PATH` | - | Path to project Obsidian vault |
| `OBSIDIAN_PERSONAL_VAULT_PATH` | - | Path to personal Obsidian vault |

## Project Structure

```
├── main.py                      # Application entry point
├── config/
│   ├── settings.py              # Environment variable loading
│   ├── logging_config.py        # Centralized logging setup
│   ├── models.json              # AI model configurations
│   ├── projects.json            # Project mappings (auto-updated)
│   └── monitored_paths.json     # Filesystem monitoring config
├── collectors/
│   ├── base_collector.py        # Abstract base class
│   ├── github_collector.py
│   ├── filesystem_collector.py
│   ├── chrome_collector.py
│   ├── gmail_collector.py
│   └── gcal_collector.py
├── processors/
│   ├── session_grouper.py       # Group events into sessions
│   ├── activity_classifier.py   # Heuristic project assignment
│   ├── daily_processor.py       # Orchestrate daily AI processing
│   ├── weekly_synthesizer.py    # Orchestrate weekly synthesis
│   └── cache_manager.py         # Webpage summary caching
├── storage/
│   ├── sqlite_manager.py        # SQLite operations
│   ├── graph_manager.py         # Neo4j operations
│   └── obsidian_writer.py       # Markdown file generation
├── ai/
│   ├── langchain_client.py      # LangChain + OpenRouter setup
│   ├── prompts/                 # Prompt templates
│   └── chains/                  # JSON output parsing
├── generators/
│   ├── activity_logger.py       # Generate activity-log.md
│   ├── project_updater.py       # Update project configs
│   ├── tweet_drafter.py         # Generate tweet drafts
│   └── templates/               # Jinja2 templates
├── scheduler/
│   └── tasks.py                 # APScheduler job definitions
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Obsidian Output

### Project Vault

Each project gets its own folder:

```
Projects/
├── home-automation/
│   ├── README.md          # Updated weekly by AI
│   └── activity-log.md    # Last 7 days, regenerated from DB
├── garden-sensors/
│   ├── README.md
│   └── activity-log.md
```

### Personal Vault

```
Personal/
└── activity-log.md        # Non-project activities
```

## Deployment

The system is designed to run as a Docker container with Neo4j as a companion service. Deploy via Docker Compose or Portainer. The GitHub Actions workflow automatically builds and pushes the Docker image to GHCR on pushes to main.

## License

Private project.
