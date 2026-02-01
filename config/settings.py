"""
Application settings loaded from environment variables.

All configuration is read from os.environ with sensible defaults where
appropriate.  Import the module-level ``settings`` instance to access
values throughout the application:

    from config.settings import settings
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Resolved project root: two levels up from this file (config/settings.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str | None = None) -> str:
    """Return an environment variable, or *default* if unset/empty."""
    value = os.environ.get(key, "")
    if value:
        return value
    if default is not None:
        return default
    return ""


def _env_int(key: str, default: int) -> int:
    """Return an environment variable cast to int, with a fallback."""
    raw = os.environ.get(key, "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            return default
    return default


@dataclass(frozen=True)
class Settings:
    """Immutable application-wide settings populated from the environment."""

    # ---- GitHub ----
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN"))
    github_username: str = field(default_factory=lambda: _env("GITHUB_USERNAME"))

    # ---- Chrome History (OAuth) ----
    chrome_client_id: str = field(default_factory=lambda: _env("CHROME_CLIENT_ID"))
    chrome_client_secret: str = field(
        default_factory=lambda: _env("CHROME_CLIENT_SECRET")
    )
    chrome_refresh_token: str = field(
        default_factory=lambda: _env("CHROME_REFRESH_TOKEN")
    )

    # ---- Google APIs (Gmail / Calendar) ----
    gmail_credentials_json: str = field(
        default_factory=lambda: _env("GMAIL_CREDENTIALS_JSON")
    )
    gcal_credentials_json: str = field(
        default_factory=lambda: _env("GCAL_CREDENTIALS_JSON")
    )

    # ---- AI / LLM ----
    openrouter_api_key: str = field(
        default_factory=lambda: _env("OPENROUTER_API_KEY")
    )

    # ---- Neo4j ----
    neo4j_uri: str = field(
        default_factory=lambda: _env("NEO4J_URI", "bolt://neo4j:7687")
    )
    neo4j_user: str = field(
        default_factory=lambda: _env("NEO4J_USER", "neo4j")
    )
    neo4j_password: str = field(default_factory=lambda: _env("NEO4J_PASSWORD"))

    # ---- Obsidian Vaults ----
    obsidian_project_vault_path: str = field(
        default_factory=lambda: _env("OBSIDIAN_PROJECT_VAULT_PATH")
    )
    obsidian_personal_vault_path: str = field(
        default_factory=lambda: _env("OBSIDIAN_PERSONAL_VAULT_PATH")
    )

    # ---- Processing Tunables ----
    session_gap_minutes: int = field(
        default_factory=lambda: _env_int("SESSION_GAP_MINUTES", 60)
    )
    processing_interval_hours: int = field(
        default_factory=lambda: _env_int("PROCESSING_INTERVAL_HOURS", 6)
    )
    max_context_chars: int = field(
        default_factory=lambda: _env_int("MAX_CONTEXT_CHARS", 50_000)
    )
    cache_expiry_days: int = field(
        default_factory=lambda: _env_int("CACHE_EXPIRY_DAYS", 7)
    )
    activity_log_days: int = field(
        default_factory=lambda: _env_int("ACTIVITY_LOG_DAYS", 7)
    )

    # ---- Storage ----
    sqlite_db_path: str = field(
        default_factory=lambda: _env(
            "SQLITE_DB_PATH", str(_PROJECT_ROOT / "data" / "activity.db")
        )
    )

    # ---- Logging ----
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))

    # ---- Timezone ----
    tz: str = field(default_factory=lambda: _env("TZ"))

    # ---- Derived Helpers ----
    @property
    def project_root(self) -> Path:
        """Absolute path to the repository root."""
        return _PROJECT_ROOT

    @property
    def logs_dir(self) -> Path:
        return _PROJECT_ROOT / "logs"

    @property
    def data_dir(self) -> Path:
        return _PROJECT_ROOT / "data"


# Module-level singleton -- import this everywhere.
settings = Settings()

# ---------------------------------------------------------------------------
# Module-level convenience aliases
# ---------------------------------------------------------------------------
# These allow collectors and other modules to write:
#     from config.settings import GITHUB_TOKEN, DATA_DIR
# instead of accessing settings.github_token each time.

GITHUB_TOKEN: str = settings.github_token
GITHUB_USERNAME: str = settings.github_username

CHROME_CLIENT_ID: str = settings.chrome_client_id
CHROME_CLIENT_SECRET: str = settings.chrome_client_secret
CHROME_REFRESH_TOKEN: str = settings.chrome_refresh_token

GMAIL_CREDENTIALS_JSON: str = settings.gmail_credentials_json
GCAL_CREDENTIALS_JSON: str = settings.gcal_credentials_json

SQLITE_DB_PATH: str = settings.sqlite_db_path

DATA_DIR: str = str(settings.data_dir)
CONFIG_DIR: str = str(_PROJECT_ROOT / "config")
LOGS_DIR: str = str(settings.logs_dir)
OUTPUTS_DIR: str = str(_PROJECT_ROOT / "outputs")

OPENROUTER_API_KEY: str = settings.openrouter_api_key

NEO4J_URI: str = settings.neo4j_uri
NEO4J_USER: str = settings.neo4j_user
NEO4J_PASSWORD: str = settings.neo4j_password

OBSIDIAN_PROJECT_VAULT_PATH: str = settings.obsidian_project_vault_path
OBSIDIAN_PERSONAL_VAULT_PATH: str = settings.obsidian_personal_vault_path

SESSION_GAP_MINUTES: int = settings.session_gap_minutes
PROCESSING_INTERVAL_HOURS: int = settings.processing_interval_hours
MAX_CONTEXT_CHARS: int = settings.max_context_chars
CACHE_EXPIRY_DAYS: int = settings.cache_expiry_days
ACTIVITY_LOG_DAYS: int = settings.activity_log_days
