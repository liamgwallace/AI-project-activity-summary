"""
Centralised logging configuration.

Call ``setup_logging()`` once at application startup (e.g. in ``main.py``)
to initialise all loggers.  After that, any module can simply do:

    import logging
    logger = logging.getLogger(__name__)

Handlers
--------
* **app**   -- ``logs/app.log``   RotatingFileHandler, 10 MB, 5 backups, INFO
* **task**  -- ``logs/tasks.log`` TimedRotatingFileHandler, midnight, 30 days, DEBUG
* **db**    -- ``logs/db.log``    RotatingFileHandler, 10 MB, 5 backups, INFO
* **console** -- stderr, for interactive development
"""

from __future__ import annotations

import logging
import logging.config
import os
from pathlib import Path

from config.settings import settings

_TEN_MB = 10 * 1024 * 1024  # 10 485 760 bytes


def _log_dir() -> str:
    """Ensure the logs directory exists and return its absolute path."""
    log_path = settings.logs_dir
    log_path.mkdir(parents=True, exist_ok=True)
    return str(log_path)


def _build_config() -> dict:
    """Build a ``logging.config.dictConfig``-compatible dictionary."""
    log_dir = _log_dir()
    level = settings.log_level.upper()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        # -- Formatters -------------------------------------------------
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "verbose": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)s | "
                    "%(funcName)s:%(lineno)d | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        # -- Handlers ---------------------------------------------------
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "standard",
                "stream": "ext://sys.stderr",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": os.path.join(log_dir, "app.log"),
                "maxBytes": _TEN_MB,
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "task_file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "verbose",
                "filename": os.path.join(log_dir, "tasks.log"),
                "when": "midnight",
                "backupCount": 30,
                "encoding": "utf-8",
            },
            "db_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "standard",
                "filename": os.path.join(log_dir, "db.log"),
                "maxBytes": _TEN_MB,
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        # -- Loggers ----------------------------------------------------
        "loggers": {
            "app": {
                "level": level,
                "handlers": ["console", "app_file"],
                "propagate": False,
            },
            "tasks": {
                "level": "DEBUG",
                "handlers": ["console", "task_file"],
                "propagate": False,
            },
            "db": {
                "level": "INFO",
                "handlers": ["console", "db_file"],
                "propagate": False,
            },
        },
        # -- Root logger (catch-all) ------------------------------------
        "root": {
            "level": level,
            "handlers": ["console", "app_file"],
        },
    }


def setup_logging() -> None:
    """Initialise application-wide logging.

    Safe to call more than once -- subsequent calls simply reconfigure.
    """
    config = _build_config()
    logging.config.dictConfig(config)
    logging.getLogger("app").debug(
        "Logging initialised (level=%s)", settings.log_level
    )
