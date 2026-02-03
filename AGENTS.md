# AGENTS.md - Agentic Coding Guidelines for PAIS

## Project Overview

Personal Activity Intelligence System (PAIS) - A Python 3.12 application that collects activity data from GitHub, Gmail, Google Calendar, and browser history, processes it with AI (OpenRouter/OpenAI), and outputs organized notes to Obsidian vaults.

## Build/Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run with Docker
docker-compose up -d

# Run with Docker (build first)
docker-compose build && docker-compose up -d
```

## Testing Commands

```bash
# Run pytest (when tests exist)
pytest

# Run specific test file
pytest tests/test_file.py

# Run single test
pytest tests/test_file.py::test_function_name

# Run with verbose output
pytest -v

# Integration tests via CLI
python -m cli.commands test-db
python -m cli.commands test-ai
python -m cli.commands test-github --store
python -m cli.commands test-gmail
python -m cli.commands test-calendar

# Collect data from all sources
python -m cli.commands collect-all

# Process unprocessed events
python -m cli.commands process-now --limit 100
```

## Code Style Guidelines

### Imports (Ordered)

1. Standard library imports (alphabetical)
2. Third-party imports (alphabetical)
3. Local application imports (alphabetical)

```python
# Standard library
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party
from fastapi import FastAPI
from pydantic import BaseModel

# Local
from config.settings import get_settings
from storage.database import Database
```

### Type Hints

- Use type hints for all function parameters and return types
- Use `Optional[X]` for nullable values
- Use `List[Dict[str, Any]]` for collections
- Use `from __future__ import annotations` when needed for forward references

### Naming Conventions

- **Functions/Variables**: `snake_case` (e.g., `get_settings`, `raw_events`)
- **Classes**: `PascalCase` (e.g., `BaseCollector`, `AIProcessor`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DAILY_PROCESS_PROMPT`)
- **Private**: Leading underscore (e.g., `_setup_logging`, `_init_tables`)
- **Modules**: `snake_case.py`

### Docstrings

Use Google-style docstrings:

```python
def process_events(self, events: List[Dict[str, Any]]) -> ProcessingResult:
    """Process a batch of events using AI.
    
    Args:
        events: List of raw event dictionaries to process.
        
    Returns:
        ProcessingResult containing extracted activities and metadata.
        
    Raises:
        ValueError: If events list is empty.
    """
```

### Error Handling

- Use specific exceptions, catch generic only as fallback
- Always log exceptions with context
- Use `try/except/finally` for resource cleanup
- Use tenacity for retry logic on external API calls

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RequestException)
)
def fetch_data():
    pass
```

### Logging

- Use module-level logger: `logger = logging.getLogger(__name__)`
- Use appropriate levels: `debug`, `info`, `warning`, `error`
- Include context in log messages
- Set third-party loggers to WARNING in `setup_logging()`

### Configuration

- Use dataclasses for config structures (`@dataclass`)
- Environment variables via `.env` file
- Access settings via singleton: `get_settings()`

### Database

- SQLite with sqlite3 module
- Use parameterized queries (never f-strings for SQL)
- Use context managers for connections: `with self._get_connection() as conn`
- Use row factory for dict-like access

### API Development

- Use FastAPI with Pydantic models
- Define request/response models as classes inheriting `BaseModel`
- Use dependency injection for auth: `Depends(verify_api_key)`
- Use async context managers for lifespan events

### Project Structure

```
PAIS/
├── api/              # FastAPI server
├── cli/              # Command-line interface
├── collectors/       # Data collectors (GitHub, Gmail, etc.)
├── config/           # Configuration management
├── processing/       # AI processing logic
├── storage/          # Database and Obsidian output
├── data/             # SQLite database (gitignored)
├── logs/             # Log files (gitignored)
└── config/           # Credentials and tokens (gitignored)
```

### Environment Variables

All config uses `PAIS_` prefix:

- `PAIS_GITHUB_TOKEN` - GitHub personal access token
- `PAIS_OPENAI_API_KEY` - OpenRouter or OpenAI API key
- `PAIS_DB_PATH` - Path to SQLite database
- `PAIS_DATA_DIR`, `PAIS_LOG_DIR`, `PAIS_CONFIG_DIR` - Directories

### Key Dependencies

- `fastapi`, `uvicorn` - API server
- `pydantic`, `pydantic-settings` - Data validation
- `langchain`, `langchain-openai` - AI integration
- `PyGithub` - GitHub API
- `google-api-python-client` - Google APIs
- `apscheduler` - Background scheduling
- `pytest`, `pytest-asyncio` - Testing

## Pre-commit Checklist

Before committing code:

1. Run tests: `pytest`
2. Check imports are sorted (stdlib → third-party → local)
3. Verify type hints on all public functions
4. Add docstrings to new functions/classes
5. Check error handling includes logging
6. Verify no hardcoded secrets or credentials
7. Test CLI commands work: `python -m cli.commands test-db`
