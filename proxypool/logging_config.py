"""
Structured logging configuration with JSON formatter.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add file/line info for DEBUG level
        if record.levelno == logging.DEBUG:
            log_data["file"] = record.filename
            log_data["line"] = record.lineno

        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True) -> None:
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        logger_name = record.name.split(".")[-1]  # Short name

        if self.use_colors:
            color = self.COLORS.get(record.levelno, "")
            level = f"{color}{level}{self.RESET}"

        msg = f"{timestamp} {level} [{logger_name}] {record.getMessage()}"

        if record.exc_info and record.exc_info[0] is not None:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    level: int = logging.INFO,
    json_output: bool = False,
    log_file: str | None = None,
) -> None:
    """
    Setup structured logging configuration.

    Args:
        level: Logging level (default: INFO)
        json_output: If True, use JSON formatter; otherwise use human-readable
        log_file: Optional log file path
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        use_colors = sys.stdout.isatty()
        console_handler.setFormatter(HumanReadableFormatter(use_colors=use_colors))

    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)
