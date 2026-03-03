"""
Centralized logging configuration for CompSphere.

Provides:
- JSON structured logging (file output for production analysis)
- Colored console logging (for development)
- Per-request correlation IDs via contextvars
- Rotating log files (app.log, error.log)
- Configurable log levels per module
"""

import logging
import logging.handlers
import json
import os
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

# ── Context variables for request-scoped data ──────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

LOG_DIR = os.getenv("LOG_DIR", "/tmp/compsphere-logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"


class JSONFormatter(logging.Formatter):
    """Outputs each log record as a single JSON line for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": request_id_var.get("-"),
            "user_id": user_id_var.get("-"),
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Attach any extra fields passed via `extra={"key": "val"}`
        for key in ("task_id", "session_id", "container_id", "endpoint",
                     "method", "status_code", "duration_ms", "client_ip",
                     "ws_event", "error_context"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Human-readable colored output for terminal use."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[41m",  # red bg
    }
    RESET = "\033[0m"
    GREY = "\033[90m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        rid = request_id_var.get("-")
        uid = user_id_var.get("-")

        prefix = f"{self.GREY}{datetime.now(timezone.utc).strftime('%H:%M:%S.%f')[:-3]}{self.RESET}"
        level = f"{color}{record.levelname:<8}{self.RESET}"
        ctx = f"{self.GREY}[rid={rid[:8]}]{self.RESET}" if rid != "-" else ""
        user_ctx = f"{self.GREY}[uid={uid[:8]}]{self.RESET}" if uid != "-" else ""
        name = f"{self.GREY}{record.name}{self.RESET}"

        msg = f"{prefix} {level} {ctx}{user_ctx} {name} :: {record.getMessage()}"

        if record.exc_info and record.exc_info[1]:
            msg += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return msg


def setup_logging() -> None:
    """Initialize the logging system. Call once at app startup."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Clear any existing handlers (prevents duplicates on reload)
    root_logger.handlers.clear()

    # ── Console handler ────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    if LOG_FORMAT == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredConsoleFormatter())
    root_logger.addHandler(console_handler)

    # ── File handlers (always JSON for analysis) ───────────────────────
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    # All logs (rotated at 10MB, keep 5 backups)
    app_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(app_handler)

    # Error-only log (for quick error scanning)
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # ── Quieten noisy third-party loggers ──────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialized",
        extra={"error_context": f"level={LOG_LEVEL}, format={LOG_FORMAT}, dir={LOG_DIR}"},
    )


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use this instead of logging.getLogger() directly."""
    return logging.getLogger(name)
