"""Start the server to handle OAuth callbacks and email webhooks."""

import os
import sys
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.util import CommandError
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

_ = load_dotenv()

from module.logger import get_logger, redirect_stderr_to_logger  # noqa: E402

if TYPE_CHECKING:
    from server.server import Server

logger = get_logger(__name__)


def run_migrations() -> None:
    """Apply database migrations before accepting traffic."""
    logger.info("Running database migrations...")
    config = Config("alembic.ini")
    upgrade_database(config, "head")
    logger.info("Database migrations complete.")


def upgrade_database(config: Config, revision: str) -> None:
    """Run Alembic upgrade for the configured database."""
    command.upgrade(config, revision)


def should_redirect_stderr() -> bool:
    """Redirect stderr only when logs are going to a file."""
    configured_log_file = os.getenv("GORDIE_LOG_FILE")
    if configured_log_file is None:
        return True

    return configured_log_file.strip().lower() not in {"", "stderr", "console", "none"}


def create_server(host: str, port: int) -> "Server":
    """Import and create the server after migrations complete."""
    from server.server import Server

    return Server(host=host, port=port)


def main() -> None:
    """Start the server."""
    host = os.getenv("SERVER_HOST", "localhost")
    port = int(os.getenv("SERVER_PORT", "8000"))

    try:
        run_migrations()
        if should_redirect_stderr():
            redirect_stderr_to_logger(logger)
        logger.info(f"Starting server on {host}:{port}...")
        server = create_server(host=host, port=port)
        logger.info(f"Server running at http://{host}:{port}")
        server.run()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        sys.exit(0)
    except (CommandError, OSError, RuntimeError, SQLAlchemyError, ValueError) as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
