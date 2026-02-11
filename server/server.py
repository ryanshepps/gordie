"""
HTTP Server for handling OAuth callbacks and email webhooks.

This module provides the Flask server that handles incoming HTTP requests
for OAuth authentication and email processing.
"""

import atexit
import logging
import threading
from typing import cast

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from prometheus_client import make_wsgi_app
from prometheus_flask_exporter import PrometheusMetrics
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from module.metrics import update_business_metrics, update_system_metrics
from scheduled.jobs import register_scheduled_jobs
from server.routes.admin_routes import register_admin_routes
from server.routes.email_routes import register_email_routes
from server.routes.oauth_routes import register_oauth_routes
from server.routes.signup_routes import register_signup_routes

# Suppress Flask's default logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Global singleton server instance
_server_instance: "Server | None" = None
_server_lock = threading.Lock()


class Server:
    """
    Flask server for handling OAuth callbacks and email webhooks.

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
        self.app = Flask(__name__)
        self.server_thread: threading.Thread | None = None

        # Instrument Flask with OpenTelemetry (TracerProvider is set up by module.tracing.init())
        FlaskInstrumentor().instrument_app(self.app)

        # Initialize Prometheus metrics for Flask
        # path=None disables automatic endpoint (we create custom /metrics endpoint later)
        self.metrics = PrometheusMetrics(self.app, path=cast(str, cast(object, None)), defaults_prefix="fantasy_agent_flask")

        # Set up periodic metrics updates
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(func=update_system_metrics, trigger="interval", seconds=15)
        self.scheduler.add_job(func=update_business_metrics, trigger="interval", seconds=60)
        self.scheduler.start()

        # Register scheduled notification jobs
        register_scheduled_jobs(self.scheduler)

        # Shut down the scheduler when exiting
        atexit.register(lambda: self.scheduler.shutdown())

        # Set up routes
        self._setup_routes()

    def _setup_routes(self):
        """Configure Flask routes."""
        # Register route handlers from separate modules
        register_oauth_routes(self.app)
        register_email_routes(self.app)
        register_signup_routes(self.app)
        register_admin_routes(self.app)

        # Health check stays inline since it's trivial
        @self.app.route("/health")
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})

        # Prometheus metrics endpoint
        @self.app.route("/metrics")
        def metrics():
            """Prometheus metrics endpoint."""
            metrics_app = make_wsgi_app()
            return metrics_app

    def start(self):
        """
        Start the server in a background thread.

        The server runs in daemon mode so it won't prevent the
        main program from exiting.
        """

        def run_server():
            # Add prometheus wsgi middleware to serve /metrics
            self.app.wsgi_app = DispatcherMiddleware(
                self.app.wsgi_app, {"/metrics": make_wsgi_app()}
            )

            self.app.run(
                host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True
            )

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give the server a moment to start
        import time

        time.sleep(1)

