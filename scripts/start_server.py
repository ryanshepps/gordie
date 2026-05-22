"""Start the server to handle OAuth callbacks and email webhooks."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from module.logger import get_logger, redirect_stderr_to_logger  # noqa: E402
from server.server import Server  # noqa: E402

logger = get_logger(__name__)


def main():
    """Start the server."""
    redirect_stderr_to_logger(logger)

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
