"""
Configuration management with singleton pattern.
Supports loading from environment variables and config files.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

SETTINGS_INSTANCE: Optional["Settings"] = None


@dataclass
class DatabaseConfig:
    path: str = "data/activity_system.db"


@dataclass
class GithubConfig:
    token: str = ""
    username: str = ""
    repos: list = field(default_factory=list)
    fetch_commits: bool = True
    fetch_prs: bool = True
    fetch_issues: bool = True
    fetch_reviews: bool = True


@dataclass
class GmailConfig:
    credentials_path: str = ""
    token_path: str = "config/gmail_token.json"
    query_days: int = 7
    labels: list = field(default_factory=lambda: ["INBOX", "SENT"])


@dataclass
class CalendarConfig:
    credentials_path: str = ""
    token_path: str = "config/calendar_token.json"
    calendars: list = field(default_factory=list)


@dataclass
class OpenAIConfig:
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 2000
    embedding_model: str = "text-embedding-3-small"


@dataclass
class Project:
    name: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    active: bool = True
    created_at: str = ""


@dataclass
class Settings:
    app_name: str = "Personal Activity Intelligence System"
    version: str = "1.0.0"
    debug: bool = False
    data_dir: str = "data"
    log_dir: str = "logs"
    config_dir: str = "config"
    
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    github: GithubConfig = field(default_factory=GithubConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    projects: Dict[str, Project] = field(default_factory=dict)
    
    def __post_init__(self):
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)


def load_settings(config_file: Optional[str] = None) -> Settings:
    """
    Load settings from environment variables and optional config file.
    Singleton pattern - subsequent calls return the same instance.
    """
    global SETTINGS_INSTANCE
    
    if SETTINGS_INSTANCE is not None:
        return SETTINGS_INSTANCE
    
    settings = Settings()
    
    # Load from environment variables
    settings.debug = os.getenv("PAIS_DEBUG", "false").lower() == "true"
    settings.data_dir = os.getenv("PAIS_DATA_DIR", "data")
    settings.log_dir = os.getenv("PAIS_LOG_DIR", "logs")
    settings.config_dir = os.getenv("PAIS_CONFIG_DIR", "config")
    
    # Database config
    settings.database.path = os.getenv("PAIS_DB_PATH", "data/activity_system.db")
    
    # GitHub config
    settings.github.token = os.getenv("PAIS_GITHUB_TOKEN", "")
    settings.github.username = os.getenv("PAIS_GITHUB_USERNAME", "")
    if os.getenv("PAIS_GITHUB_REPOS"):
        settings.github.repos = os.getenv("PAIS_GITHUB_REPOS", "").split(",")
    
    # Gmail config
    settings.gmail.credentials_path = os.getenv("PAIS_GMAIL_CREDENTIALS_PATH", "")
    settings.gmail.token_path = os.getenv("PAIS_GMAIL_TOKEN_PATH", "config/gmail_token.json")
    if os.getenv("PAIS_GMAIL_LABELS"):
        settings.gmail.labels = os.getenv("PAIS_GMAIL_LABELS", "").split(",")
    
    # Calendar config
    settings.calendar.credentials_path = os.getenv("PAIS_CALENDAR_CREDENTIALS_PATH", "")
    settings.calendar.token_path = os.getenv("PAIS_CALENDAR_TOKEN_PATH", "config/calendar_token.json")
    
    # OpenAI config
    settings.openai.api_key = os.getenv("PAIS_OPENAI_API_KEY", "")
    settings.openai.model = os.getenv("PAIS_OPENAI_MODEL", "gpt-4o-mini")
    settings.openai.temperature = float(os.getenv("PAIS_OPENAI_TEMPERATURE", "0.3"))
    settings.openai.max_tokens = int(os.getenv("PAIS_OPENAI_MAX_TOKENS", "2000"))
    settings.openai.embedding_model = os.getenv("PAIS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Load from config file if provided
    if config_file and Path(config_file).exists():
        with open(config_file, "r") as f:
            config_data = json.load(f)
            settings = _merge_config_data(settings, config_data)
    
    # Load projects from config file if it exists
    projects_file = Path(settings.config_dir) / "projects.json"
    if projects_file.exists():
        with open(projects_file, "r") as f:
            projects_data = json.load(f)
            for name, data in projects_data.items():
                settings.projects[name] = Project(
                    name=name,
                    description=data.get("description", ""),
                    tags=data.get("tags", []),
                    keywords=data.get("keywords", []),
                    active=data.get("active", True),
                    created_at=data.get("created_at", "")
                )
    
    SETTINGS_INSTANCE = settings
    return settings


def _merge_config_data(settings: Settings, data: Dict[str, Any]) -> Settings:
    """Merge dictionary config data into settings object."""
    if "database" in data:
        for key, value in data["database"].items():
            if hasattr(settings.database, key):
                setattr(settings.database, key, value)
    
    if "github" in data:
        for key, value in data["github"].items():
            if hasattr(settings.github, key):
                setattr(settings.github, key, value)
    
    if "gmail" in data:
        for key, value in data["gmail"].items():
            if hasattr(settings.gmail, key):
                setattr(settings.gmail, key, value)
    
    if "calendar" in data:
        for key, value in data["calendar"].items():
            if hasattr(settings.calendar, key):
                setattr(settings.calendar, key, value)
    
    if "openai" in data:
        for key, value in data["openai"].items():
            if hasattr(settings.openai, key):
                setattr(settings.openai, key, value)
    
    return settings


def get_settings() -> Settings:
    """Get the singleton settings instance. Loads if not already loaded."""
    if SETTINGS_INSTANCE is None:
        return load_settings()
    return SETTINGS_INSTANCE


def get_model_config(model_name: str = "default") -> Dict[str, Any]:
    """
    Get configuration for a specific AI model.
    
    Args:
        model_name: Name of the model configuration to retrieve
        
    Returns:
        Dictionary containing model configuration
    """
    settings = get_settings()
    
    configs = {
        "default": {
            "model": settings.openai.model,
            "temperature": settings.openai.temperature,
            "max_tokens": settings.openai.max_tokens,
        },
        "summarization": {
            "model": settings.openai.model,
            "temperature": 0.2,
            "max_tokens": 1500,
        },
        "classification": {
            "model": settings.openai.model,
            "temperature": 0.1,
            "max_tokens": 500,
        },
        "tweet": {
            "model": settings.openai.model,
            "temperature": 0.7,
            "max_tokens": 500,
        },
        "embedding": {
            "model": settings.openai.embedding_model,
        },
    }
    
    return configs.get(model_name, configs["default"])


def get_project(project_name: str) -> Optional[Project]:
    """Get project configuration by name."""
    settings = get_settings()
    return settings.projects.get(project_name)


def save_project(project: Project) -> None:
    """Save or update a project configuration."""
    settings = get_settings()
    settings.projects[project.name] = project
    
    # Save to file
    projects_file = Path(settings.config_dir) / "projects.json"
    projects_data = {}
    
    if projects_file.exists():
        with open(projects_file, "r") as f:
            projects_data = json.load(f)
    
    projects_data[project.name] = {
        "description": project.description,
        "tags": project.tags,
        "keywords": project.keywords,
        "active": project.active,
        "created_at": project.created_at,
    }
    
    with open(projects_file, "w") as f:
        json.dump(projects_data, f, indent=2)
