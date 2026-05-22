"""
HTTP Server for handling OAuth callbacks and email webhooks.

This module provides the Quart server that handles incoming HTTP requests
for OAuth authentication and email processing.
"""

import asyncio
import atexit
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart, jsonify

import billing
from agent.checkpointer import (
    checkpointer,  # noqa: F401 — ensures checkpoint tables exist at startup
)
from module.logger import get_logger
from scheduled.jobs import register_scheduled_jobs
from server.routes.email_routes import register_email_routes
from server.routes.oauth_routes import register_oauth_routes
from server.routes.signup_routes import register_signup_routes
from server.routes.sms_routes import register_sms_routes

# Suppress Hypercorn's default access logging
logging.getLogger("hypercorn.access").setLevel(logging.ERROR)

# Global singleton server instance
_server_instance: "Server | None" = None
_server_lock = threading.Lock()


class Server:
    """
    Quart server for handling OAuth callbacks and email webhooks.

    The server listens on the configured host/port and handles:
    - /callback - OAuth authorization code redirects from Yahoo
    - /email/webhook - Incoming email notifications from Mailgun
    - /health - Health check endpoint
    """

    def __init__(self, host: str, port: int) -> None:
        """
        Initialize the server.

        Args:
            host: Host to bind the server to (e.g., "localhost")
            port: Port to listen on (e.g., 8000)
        """
        billing.validate_billing_config()

        self.host = host
        self.port = port
        self.app = Quart(__name__)

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        # Register scheduled notification jobs
        register_scheduled_jobs(self.scheduler)

        # Ensure stats DB exists on first deploy
        threading.Thread(target=self._refresh_stats_db_on_startup, daemon=True).start()

        # Shut down the scheduler when exiting
        atexit.register(lambda: self.scheduler.shutdown())

        # Set up routes
        self._setup_routes()

    @staticmethod
    def _refresh_stats_db_on_startup() -> None:
        from module.config import sport_enabled

        logger = get_logger(__name__)

        if sport_enabled("nhl"):
            try:
                from scheduled.refresh_stats_db import refresh_stats_db

                refresh_stats_db()
                logger.info("NHL stats DB refreshed on startup")
            except Exception:
                logger.exception("Failed to refresh NHL stats DB on startup")
        else:
            logger.info("NHL disabled via ENABLED_SPORTS; skipping stats refresh")

        if sport_enabled("mlb"):
            try:
                from scheduled.refresh_mlb_stats_db import refresh_mlb_stats_db

                refresh_mlb_stats_db()
                logger.info("MLB stats DB refreshed on startup")
            except Exception:
                logger.exception("Failed to refresh MLB stats DB on startup")
        else:
            logger.info("MLB disabled via ENABLED_SPORTS; skipping stats refresh")

    def _setup_routes(self):
        """Configure Quart routes."""
        # Register route handlers from separate modules
        register_oauth_routes(self.app)
        register_email_routes(self.app)
        register_signup_routes(self.app)
        register_sms_routes(self.app)
        if billing.billing_enabled:
            billing.register_routes(self.app)

        # Health check stays inline since it's trivial
        @self.app.route("/health")
        async def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})

    def run(self):
        """
        Run the server on the main thread (blocking).

        Hypercorn requires the main thread for signal handling.
        """
        logger = get_logger(__name__, log_file="server.log")

        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.errorlog = logger
        asyncio.run(serve(self.app, config))
