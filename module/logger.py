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

    def add_fields(self, log_data, record, message_dict):
        super().add_fields(log_data, record, message_dict)

        log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        log_data["level"] = record.levelname
        log_data["filename"] = Path(record.pathname).name
        log_data["function"] = record.funcName
        log_data["line"] = record.lineno

        agent_name = getattr(record, "agent_name", None)
        if agent_name is not None:
            log_data["agent_name"] = agent_name
        tool_name = getattr(record, "tool_name", None)
        if tool_name is not None:
            log_data["tool_name"] = tool_name
        user_email = getattr(record, "user_email", None)
        if user_email is not None:
            log_data["user_email"] = user_email
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms
        status = getattr(record, "status", None)
        if status is not None:
            log_data["status"] = status

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)


def _is_test_environment() -> bool:
    return "pytest" in sys.modules


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
    if _is_test_environment():
        log_file = None

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


class StderrToLogger:
    """Stream wrapper that redirects stderr writes to the logger."""

    def __init__(self, logger: logging.Logger, log_level: int = logging.ERROR):
        self.logger = logger
        self.log_level = log_level
        self.buffer = ""

    def write(self, message: str) -> int:
        """Write message to logger instead of stderr."""
        # Accumulate the message in buffer
        self.buffer += message

        # When we get a newline, log the accumulated message
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            # Log all complete lines (everything except the last item which might be incomplete)
            for line in lines[:-1]:
                if line.strip():  # Only log non-empty lines
                    self.logger.log(self.log_level, line.rstrip())
            # Keep the last incomplete part in the buffer
            self.buffer = lines[-1]

        return len(message)

    def flush(self) -> None:
        """Flush any remaining buffer content."""
        if self.buffer.strip():
            self.logger.log(self.log_level, self.buffer.rstrip())
            self.buffer = ""

    def isatty(self) -> bool:
        """Return False since this is not a TTY."""
        return False


def redirect_stderr_to_logger(logger: logging.Logger | None = None) -> None:
    """
    Redirect all stderr output to the logger as ERROR level JSON logs.

    This captures uncaught exceptions, framework errors, and any other
    stderr output and formats them as structured JSON logs.

    Args:
        logger: Logger to redirect stderr to. If None, uses root logger.

    Example:
        # In your main script
        logger = get_logger(__name__)
        redirect_stderr_to_logger(logger)
    """
    if logger is None:
        logger = logging.getLogger()

    sys.stderr = StderrToLogger(logger, logging.ERROR)  # type: ignore[assignment]
