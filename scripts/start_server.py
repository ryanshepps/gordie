"""Start the server to handle OAuth callbacks and email webhooks."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Initialize tracing BEFORE any application imports so that
# Logfire's auto-tracing can rewrite modules at import time.
from module.tracing import init  # noqa: E402

init()

from module.logger import get_logger, redirect_stderr_to_logger  # noqa: E402
from server.server import Server  # noqa: E402

logger = get_logger(__name__)


def main():
    """Start the server."""
    tracing_logger = get_logger("tracing", log_file="tracing.log")
    redirect_stderr_to_logger(tracing_logger)

    host = os.getenv("SERVER_HOST", "localhost")
    port = int(os.getenv("SERVER_PORT", "8000"))

    logger.info(f"Starting server on {host}:{port}...")
    server = Server(host=host, port=port)

    try:
        logger.info(f"Server running at http://{host}:{port}")
        server.run()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
