# Config Module

Configuration management with dataclasses and environment variables.

## Description

The config module manages all application settings using dataclasses and environment variables. Implements a singleton pattern to ensure consistent configuration across the application.

## Files

- `settings.py` - All configuration classes and loading functions
- `__init__.py` - Package initialization

## Key Classes

### Settings (Main Config)
Root configuration dataclass:
- `app_name`, `version`, `debug` - Application metadata
- `data_dir`, `log_dir`, `config_dir` - Directory paths
- `database`, `github`, `gmail`, `calendar`, `openai` - Component configs
- `projects` - Dictionary of Project objects

### Component Configs
- `DatabaseConfig` - SQLite database path
- `GithubConfig` - Token, username, repos, fetch flags
- `GmailConfig` - Credentials path, token path, labels, query days
- `CalendarConfig` - Credentials path, token path, calendars list
- `OpenAIConfig` - API key, model, temperature, max_tokens
- `Project` - Name, description, tags, keywords, active status

## Key Functions

### Configuration Loading
- `load_settings(config_file=None)` - Load from environment and optional JSON file
- `get_settings()` - Get singleton settings instance
- `_merge_config_data(settings, data)` - Merge dict into settings object

### Model Configuration
- `get_model_config(model_name)` - Get AI model presets (default, summarization, classification, tweet, embedding)

### Project Management
- `get_project(name)` - Retrieve project by name
- `save_project(project)` - Save project to JSON file

## Environment Variables

All variables use `PAIS_` prefix:
```bash
PAIS_DEBUG=true
PAIS_DATA_DIR=data
PAIS_DB_PATH=data/activity_system.db
PAIS_GITHUB_TOKEN=ghp_xxx
PAIS_GITHUB_USERNAME=user
PAIS_GMAIL_CREDENTIALS_PATH=config/gmail_credentials.json
PAIS_GMAIL_TOKEN_PATH=data/gmail_token.json
PAIS_CALENDAR_CREDENTIALS_PATH=config/calendar_credentials.json
PAIS_CALENDAR_TOKEN_PATH=data/calendar_token.json
PAIS_OPENAI_API_KEY=sk-xxx
PAIS_OPENAI_MODEL=gpt-4o-mini
PAIS_OPENAI_TEMPERATURE=0.3
```

**Note on Google OAuth Files:**
- **Credentials** (`*_credentials.json`) - Downloaded from Google Cloud Console, stored in `config/` (static, read-only)
- **Tokens** (`*_token.json`) - Generated on first OAuth flow, stored in `data/` (dynamic, read-write)
- This separation allows credentials to be mounted read-only in Docker while tokens remain writable

## Usage

```python
from config.settings import load_settings, get_settings, get_model_config

# Load settings (singleton)
load_settings()
settings = get_settings()

# Access configuration
print(settings.github.token)
print(settings.openai.model)

# Get model preset
model_config = get_model_config("summarization")
```

## Project Configuration

Projects are stored in `config/projects.json`:
```json
{
  "project-name": {
    "description": "Project description",
    "tags": ["tag1", "tag2"],
    "keywords": ["keyword1", "keyword2"],
    "active": true
  }
}
```
