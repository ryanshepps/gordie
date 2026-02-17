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
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from quart import Quart, jsonify

from agent.checkpointer import (
    checkpointer,  # noqa: F401 — ensures checkpoint tables exist at startup
)
from module.metrics import update_business_metrics, update_system_metrics
from scheduled.jobs import register_scheduled_jobs
from server.routes.admin_routes import register_admin_routes
from server.routes.email_routes import register_email_routes
from server.routes.oauth_routes import register_oauth_routes
from server.routes.signup_routes import register_signup_routes
from server.routes.sms_routes import register_sms_routes

# Suppress Hypercorn's default access logging
logging.getLogger("hypercorn.access").setLevel(logging.ERROR)

# Global singleton server instance
_server_instance: "Server | None" = None
_server_lock = threading.Lock()


async def _shutdown_async_agent() -> None:
    """Shut down the async agent connection if it was initialized."""
    from agent.async_graph_builder import close_async_agent

    await close_async_agent()


class Server:
    """
    Quart server for handling OAuth callbacks and email webhooks.

    The server listens on the configured host/port and handles:
    - /callback - OAuth authorization code redirects from Yahoo
    - /email/webhook - Incoming email notifications from Mailgun
    - /health - Health check endpoint
    """

    def __init__(self, host: str, port: int):
        """
        Initialize the server.

        Args:
            host: Host to bind the server to (e.g., "localhost")
            port: Port to listen on (e.g., 8000)
        """
        self.host = host
        self.port = port
        self.app = Quart(__name__)

        # Instrument with OpenTelemetry via ASGI middleware.
        # Type ignore: OpenTelemetry types ASGI params as MutableMapping[str, Any] while
        # Quart/Hypercorn use narrower TypedDict aliases — both follow the ASGI 3.0 spec.
        self.app.asgi_app = OpenTelemetryMiddleware(self.app.asgi_app)  # pyright: ignore[reportAttributeAccessIssue]

        # Set up periodic metrics updates
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(func=update_system_metrics, trigger="interval", seconds=15)
        self.scheduler.add_job(func=update_business_metrics, trigger="interval", seconds=60)
        self.scheduler.start()

        # Register scheduled notification jobs
        register_scheduled_jobs(self.scheduler)

        # Shut down the scheduler and async agent when exiting
        atexit.register(lambda: self.scheduler.shutdown())
        atexit.register(lambda: asyncio.run(_shutdown_async_agent()))

        # Set up routes
        self._setup_routes()

    def _setup_routes(self):
        """Configure Quart routes."""
        # Register route handlers from separate modules
        register_oauth_routes(self.app)
        register_email_routes(self.app)
        register_signup_routes(self.app)
        register_admin_routes(self.app)
        register_sms_routes(self.app)

        # Health check stays inline since it's trivial
        @self.app.route("/health")
        async def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})

        # Prometheus metrics endpoint
        @self.app.route("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    def run(self):
        """
        Run the server on the main thread (blocking).

        Hypercorn requires the main thread for signal handling.
        """
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        asyncio.run(serve(self.app, config))
