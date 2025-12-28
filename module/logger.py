import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

from pythonjsonlogger import json as jsonlogger


class CustomFormatter(logging.Formatter):
    """Custom formatter that includes filename, timestamp, log level, and message."""

    # ANSI color codes for different log levels
    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Get the filename from the full path
        filename = Path(record.pathname).name

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Get log level with color
        level_name = record.levelname
        color = self.COLORS.get(level_name, "")

        # Format: [filename] [timestamp] [LEVEL] message
        log_format = (
            f"[{filename}] [{timestamp}] {color}[{level_name}]{self.RESET} {record.getMessage()}"
        )

        # Add exception info if present
        if record.exc_info:
            log_format += "\n" + self.formatException(record.exc_info)

        return log_format


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter for structured logging to files (for Loki ingestion)."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        log_record["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        log_record["level"] = record.levelname
        log_record["filename"] = Path(record.pathname).name
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        if hasattr(record, "agent_name"):
            log_record["agent_name"] = record.agent_name
        if hasattr(record, "tool_name"):
            log_record["tool_name"] = record.tool_name
        if hasattr(record, "user_email"):
            log_record["user_email"] = record.user_email
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms
        if hasattr(record, "status"):
            log_record["status"] = record.status

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def get_logger(
    name: str | None = None, level: int = logging.INFO, log_file: str | None = "server.log"
) -> logging.Logger:
    """
    Get a configured logger instance with JSON file handler.

    Args:
        name: Logger name (defaults to the calling module's name)
        level: Logging level (default: INFO)
        log_file: File path for JSON logs (default: "server.log"). Set to None for console logging.

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)  # Logs to server.log by default in JSON format
        logger.info("Application started")
        logger.info("Tool executed", extra={'tool_name': 'get_roster', 'duration_ms': 150})

        logger = get_logger(__name__, log_file=None)  # Console logging for debugging
    """
    logger = logging.getLogger(name or __name__)

    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.setLevel(level)

        # File handler (JSON output for Loki)
        if log_file:
            # Use RotatingFileHandler to limit log file size to 1GB
            # When the file reaches 1GB, it rotates and keeps 2 backup files
            # Total disk usage: up to 3GB (current + 2 backups)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=1073741824,  # 1GB in bytes
                backupCount=2,  # Keep 2 backup files (.1, .2)
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(
                CustomJsonFormatter("%(timestamp)s %(level)s %(filename)s %(message)s")
            )
            logger.addHandler(file_handler)
        else:
            # If no log file specified, add console handler for debugging
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(level)
            console_handler.setFormatter(CustomFormatter())
            logger.addHandler(console_handler)

    return logger
