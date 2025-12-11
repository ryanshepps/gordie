"""
OAuth Callback Server for Yahoo Fantasy OAuth flow.

This module provides a local Flask server that handles the OAuth callback
from Yahoo Fantasy Sports API during the authentication process.
"""

import threading
from typing import Optional
from flask import Flask, request, jsonify
import logging

# Suppress Flask's default logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class OAuthCallbackServer:
    """
    Local Flask server for handling Yahoo OAuth callbacks.

    The server listens on localhost:8000/callback and captures the
    authorization code from Yahoo's OAuth redirect.
    """

    def __init__(self, host: str, port: int):
        """
        Initialize the OAuth callback server.

        Args:
            host: Host to bind the server to (default: localhost)
            port: Port to listen on (default: 8000)
        """
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.server_thread: Optional[threading.Thread] = None
        self.auth_code: Optional[str] = None
        self.auth_error: Optional[str] = None
        self.code_received = threading.Event()

        # Set up Flask routes
        self._setup_routes()

    def _setup_routes(self):
        """Configure Flask routes for OAuth callback."""

        @self.app.route('/callback')
        def callback():
            """Handle OAuth callback from Yahoo."""
            # Log all query parameters for debugging
            from module.logger import get_logger
            logger = get_logger(__name__)

            # Check for authorization code
            code = request.args.get('code')
            error = request.args.get('error')
            error_description = request.args.get('error_description')

            if error:
                self.auth_error = error
                logger.error(f"OAuth Error: {error}")
                if error_description:
                    logger.error(f"Error Description: {error_description}")
                self.code_received.set()
                return """
                <html>
                    <body>
                        <h1>Authentication Error</h1>
                        <p>There was an error during authentication: {}</p>
                        <p>Error description: {}</p>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                </html>
                """.format(error, error_description or "No description provided"), 400

            if code:
                self.auth_code = code
                self.code_received.set()
                return """
                <html>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You have successfully authenticated with Yahoo Fantasy.</p>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                </html>
                """

            return """
            <html>
                <body>
                    <h1>Invalid Request</h1>
                    <p>No authorization code received.</p>
                    <p>You can close this window and return to the terminal.</p>
                </body>
            </html>
            """, 400

        @self.app.route('/health')
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})

    def start(self):
        """
        Start the OAuth callback server in a background thread.

        The server runs in daemon mode so it won't prevent the
        main program from exiting.
        """
        def run_server():
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give the server a moment to start
        import time
        time.sleep(1)

    def wait_for_code(self, timeout: Optional[float] = 300) -> Optional[str]:
        """
        Wait for the OAuth authorization code to be received.

        Args:
            timeout: Maximum time to wait in seconds (default: 300/5 minutes)
                    None means wait indefinitely.

        Returns:
            The authorization code if received, None if timeout or error occurred.

        Raises:
            RuntimeError: If an OAuth error was received from Yahoo.
        """
        code_received = self.code_received.wait(timeout=timeout)

        if not code_received:
            return None

        if self.auth_error:
            raise RuntimeError(f"OAuth error received: {self.auth_error}")

        return self.auth_code

    def shutdown(self):
        """
        Shutdown the OAuth callback server.

        Note: Flask development server doesn't support graceful shutdown
        from another thread. Since we're running in daemon mode, the
        server will automatically terminate when the main program exits.
        """
        # Reset state
        self.auth_code = None
        self.auth_error = None
        self.code_received.clear()

        # In daemon mode, the thread will terminate with the main program
        # No explicit shutdown needed

    def get_callback_url(self, base_url: str) -> str:
        """
        Get the full callback URL for OAuth configuration.

        Args:
            base_url: Custom base URL (e.g., 'https://abc123.ngrok-free.app')
                     If None, uses the default localhost URL.

        Returns:
            Full callback URL with /callback path

        Examples:
            >>> server.get_callback_url('https://abc123.ngrok-free.app')
            'https://abc123.ngrok-free.app/callback'
        """
        # Strip trailing slash if present
        base_url = base_url.rstrip('/')
        return f"{base_url}/callback"
