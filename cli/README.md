# CLI Module

Command-line interface for testing integrations and managing the PAIS system.

## Description

The CLI module provides commands for testing data collectors, running the processing pipeline, and viewing system statistics. Useful for development, debugging, and manual operations.

## Files

- `commands.py` - All CLI commands and argument parsing
- `__init__.py` - Package initialization

## Commands

### Test Commands
- `test-github [--store]` - Test GitHub API connection and fetch sample commits/PRs
- `test-gmail` - Test Gmail API and fetch recent emails
- `test-calendar` - Test Google Calendar API and fetch events
- `test-db` - Test database operations (insert, query, stats)
- `test-ai` - Test AI model connectivity with a simple prompt

### Collection Commands
- `collect-all [--skip-github] [--skip-gmail] [--skip-calendar]` - Collect data from all enabled sources

### Processing Commands
- `process-now [--limit N]` - Process unprocessed events immediately

### View Commands
- `show-events [--days N] [--limit N] [--verbose]` - Display recent events
- `show-stats [--days N]` - Show system statistics and token usage

### Report Commands
- `generate-logs [--days N] [--project NAME] [-o FILE]` - Generate activity logs

## Usage

```bash
# Run from project root
python -m cli.commands test-github
python -m cli.commands test-gmail
python -m cli.commands test-db

# Collect data from all sources
python -m cli.commands collect-all

# Process pending events
python -m cli.commands process-now --limit 50

# View recent events
python -m cli.commands show-events --days 7 --verbose

# Show statistics
python -m cli.commands show-stats --days 30
```

## Dependencies

Tests check for required libraries and prompt installation if missing:
- `PyGithub` - GitHub integration
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` - Google APIs
- `langchain`, `langchain-openai` - AI processing

## Exit Codes

- `0` - Success
- `1` - Error (missing credentials, connection failed, etc.)
