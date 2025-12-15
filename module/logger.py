import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import ClassVar


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


def get_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (defaults to the calling module's name)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
        logger.debug("Debug information")
        logger.warning("Warning message")
        logger.error("Error occurred")
    """
    logger = logging.getLogger(name or __name__)

    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.setLevel(level)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(CustomFormatter())

        logger.addHandler(console_handler)

    return logger
