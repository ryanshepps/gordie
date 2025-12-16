"""
OAuth Callback Server for Yahoo Fantasy OAuth flow.

This module provides a local Flask server that handles the OAuth callback
from Yahoo Fantasy Sports API during the authentication process, along with
the complete OAuth flow orchestration.
"""

import base64
import json
import logging
import os
import secrets
import threading
import webbrowser
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

from client.duck_db_client import get_platform_db_connection
from module.logger import get_logger

load_dotenv()

# Suppress Flask's default logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Global singleton server instance
_server_instance: Optional["OAuthCallbackServer"] = None
_server_lock = threading.Lock()


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
        self.server_thread: threading.Thread | None = None
        self.auth_code: str | None = None
        self.auth_error: str | None = None
        self.user_email: str | None = None
        self.code_received = threading.Event()

        # Set up Flask routes
        self._setup_routes()

    def _setup_routes(self):
        """Configure Flask routes for OAuth callback."""

        @self.app.route("/callback")
        def callback():
            """Handle OAuth callback from Yahoo."""
            from module.logger import get_logger

            logger = get_logger(__name__)

            # Check for authorization code
            code = request.args.get("code")
            error = request.args.get("error")
            error_description = request.args.get("error_description")
            user_email = request.args.get("state")  # user_email passed via state parameter

            if error:
                self.auth_error = error
                logger.error(f"OAuth Error: {error}")
                if error_description:
                    logger.error(f"Error Description: {error_description}")
                self.code_received.set()
                return (
                    f"""
                <html>
                    <body>
                        <h1>Authentication Error</h1>
                        <p>{error}: {error_description or "No description"}</p>
                    </body>
                </html>
                """,
                    400,
                )

            if code:
                # Prevent duplicate callbacks (browser double-requests, refreshes, etc.)
                if self.auth_code == code:
                    logger.warning("Duplicate callback detected, ignoring")
                    return """
                    <html>
                        <body>
                            <h1>Authentication Successful!</h1>
                            <p>You can close this window and return to your conversation.</p>
                        </body>
                    </html>
                    """

                self.auth_code = code
                self.user_email = user_email
                self.code_received.set()
                return """
                <html>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You can close this window and return to your conversation.</p>
                    </body>
                </html>
                """

            return (
                """
            <html>
                <body>
                    <h1>Invalid Request</h1>
                    <p>No authorization code received.</p>
                </body>
            </html>
            """,
                400,
            )

        @self.app.route("/health")
        def health():
            """Health check endpoint."""
            return jsonify({"status": "ok"})

        @self.app.route("/email/webhook", methods=["POST"])
        def email_webhook():
            """Handle incoming emails from Mailgun webhook."""
            from module.logger import get_logger

            logger = get_logger(__name__)

            # Extract webhook data
            sender_email = request.form.get("sender")
            subject = request.form.get("subject", "")
            message_body = request.form.get("stripped-text") or request.form.get("body-plain", "")
            timestamp = request.form.get("timestamp")
            token = request.form.get("token")
            signature = request.form.get("signature")

            # Validate required fields
            if not all([sender_email, timestamp, token, signature]):
                logger.error("Missing required webhook fields")
                return jsonify({"error": "Missing required fields"}), 400

            # Type assertions - we've validated these are not None above
            assert sender_email is not None
            assert timestamp is not None
            assert token is not None
            assert signature is not None

            # Verify signature and timestamp
            from server.webhook_verification import is_timestamp_fresh, verify_mailgun_webhook

            if not is_timestamp_fresh(timestamp):
                logger.error(f"Webhook timestamp too old: {timestamp}")
                return jsonify({"error": "Timestamp too old"}), 403

            if not verify_mailgun_webhook(token, timestamp, signature):
                logger.error(f"Invalid webhook signature from {sender_email}")
                return jsonify({"error": "Invalid signature"}), 403

            logger.info(f"Received email from {sender_email}: {subject}")

            # Process in background thread
            def process_email():
                try:
                    from scripts.message_agent import message_agent
                    from server.email_service import EmailService

                    # Process through agent
                    logger.info(f"Processing email from {sender_email}")
                    response = message_agent(email=sender_email, message=message_body)

                    # Send response email
                    if response:
                        email_service = EmailService()
                        success = email_service.send_email(
                            to_email=sender_email,
                            subject=f"Re: {subject}" if subject else "Fantasy Agent Response",
                            text_body=response,
                        )

                        if success:
                            logger.info(f"Response sent to {sender_email}")
                        else:
                            logger.error(f"Failed to send response to {sender_email}")

                except Exception as e:
                    logger.error(f"Error processing email from {sender_email}: {e}", exc_info=True)

            # Start background thread
            thread = threading.Thread(target=process_email, daemon=True)
            thread.start()

            # Return immediately to Mailgun
            return jsonify({"status": "received"}), 200

    def start(self):
        """
        Start the OAuth callback server in a background thread.

        The server runs in daemon mode so it won't prevent the
        main program from exiting.
        """

        def run_server():
            self.app.run(
                host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True
            )

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give the server a moment to start
        import time

        time.sleep(1)

    def wait_for_code(self, timeout: float | None = 300) -> str | None:
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
            raise RuntimeError(f"OAuth error: {self.auth_error}")

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
        self.user_email = None
        self.code_received.clear()

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
        base_url = base_url.rstrip("/")
        return f"{base_url}/callback"


# OAuth Flow Functions


def initiate_oauth_flow(user_email: str) -> dict[str, Any]:
    """
    Complete OAuth flow: start server, authorize, exchange tokens, save to DB.

    Args:
        user_email: Email address of the user to authenticate

    Returns:
        dict with access_token, refresh_token, token_time, token_type, yahoo_email

    Raises:
        ValueError: If required environment variables are missing
        RuntimeError: If OAuth flow fails at any step
    """
    logger = get_logger(__name__, level=logging.DEBUG)

    client_id = os.getenv("YAHOO_CLIENT_ID")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET")
    oauth_base_url = os.getenv("OAUTH_BASE_URL")

    if not client_id or not client_secret:
        raise ValueError("Missing YAHOO_CLIENT_ID and/or YAHOO_CLIENT_SECRET in .env")

    logger.info(f"Starting OAuth flow for user: {user_email}")
    server = OAuthCallbackServer(host="localhost", port=8000)

    try:
        server.start()
        callback_url = server.get_callback_url(oauth_base_url or "http://localhost:8000")
        logger.info(f"Callback URL: {callback_url}")

        nonce = secrets.token_urlsafe(32)
        auth_url = _build_auth_url(
            client_id, callback_url, "openid email fspt-r", nonce, state=user_email
        )

        logger.info("Opening browser for authorization...")
        logger.info(f"If browser doesn't open: {auth_url}")
        webbrowser.open(auth_url)

        logger.info("Waiting for authorization code (timeout: 5 minutes)...")
        auth_code = server.wait_for_code(timeout=300)
        if not auth_code:
            raise RuntimeError("OAuth timed out")

        logger.info("✓ Authorization code received")

        token_data = _exchange_code(auth_code, client_id, client_secret, callback_url, nonce)
        logger.info("✓ Access tokens received")

        yahoo_email = _get_yahoo_email(token_data["access_token"])
        if not yahoo_email:
            raise RuntimeError("Could not retrieve Yahoo email")

        logger.info(f"✓ Yahoo email: {yahoo_email}")
        token_data["yahoo_email"] = yahoo_email

        _save_tokens(user_email, yahoo_email, token_data)
        logger.info("✓ Tokens saved to database")

        # Notify the OnboardingAgent that OAuth is complete
        _notify_onboarding_agent(user_email)

        logger.info(f"OAuth flow completed for {user_email}")
        return token_data

    finally:
        server.shutdown()


def _build_auth_url(
    client_id: str, redirect_uri: str, scope: str, nonce: str, state: str | None = None
) -> str:
    """Build Yahoo OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "nonce": nonce,
        "language": "en-us",
    }
    if state:
        params["state"] = state
    return f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"


def _validate_nonce(id_token: str, expected_nonce: str) -> None:
    """Validate nonce in ID token."""
    logger = get_logger(__name__)

    parts = id_token.split(".")
    if len(parts) != 3:
        raise RuntimeError("Invalid ID token format")

    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding

    claims = json.loads(base64.urlsafe_b64decode(payload))
    token_nonce = claims.get("nonce")

    if token_nonce and token_nonce != expected_nonce:
        raise RuntimeError("Nonce validation failed")

    logger.debug("Nonce validated")


def _exchange_code(
    auth_code: str, client_id: str, client_secret: str, redirect_uri: str, nonce: str
) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    logger = get_logger(__name__)

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"grant_type": "authorization_code", "code": auth_code, "redirect_uri": redirect_uri}

    try:
        response = requests.post(
            "https://api.login.yahoo.com/oauth2/get_token", headers=headers, data=data, timeout=10
        )

        # Log response details before raising for better debugging
        if response.status_code != 200:
            logger.error(f"Token exchange failed with status {response.status_code}")
            logger.error(f"Response body: {response.text}")

        response.raise_for_status()
        token_response = response.json()

        token_data = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response["refresh_token"],
            "token_time": datetime.now(),
            "token_type": token_response.get("token_type", "Bearer"),
        }

        if "id_token" in token_response:
            token_data["id_token"] = token_response["id_token"]
            _validate_nonce(token_response["id_token"], nonce)
            logger.info("✓ ID token nonce validated")

        return token_data

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Token exchange failed: {e}") from e


def _get_yahoo_email(access_token: str) -> str | None:
    """Fetch Yahoo user email from userinfo endpoint."""
    logger = get_logger(__name__)

    try:
        response = requests.get(
            "https://api.login.yahoo.com/openid/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("email")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch userinfo: {e}")
        return None


def _save_tokens(user_email: str, yahoo_email: str, token_data: dict[str, Any]) -> None:
    """Save OAuth tokens to database."""
    logger = get_logger(__name__)
    conn = get_platform_db_connection()
    try:
        # Ensure user exists first (to satisfy foreign key constraint)
        _ = conn.execute(
            """
            INSERT INTO users (email) VALUES (?)
            ON CONFLICT (email) DO NOTHING
        """,
            (user_email,),
        )

        # Now insert/update tokens
        _ = conn.execute(
            """
            INSERT OR REPLACE INTO yahoo_tokens (
                user_email, yahoo_email, access_token, refresh_token,
                token_time, token_type, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                user_email,
                yahoo_email,
                token_data["access_token"],
                token_data["refresh_token"],
                token_data["token_time"],
                token_data["token_type"],
            ),
        )
        conn.commit()
        logger.debug(f"Saved tokens for user {user_email}")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to save tokens: {e}") from e
    finally:
        conn.close()


def _notify_onboarding_agent(user_email: str) -> None:
    """
    Notify the OnboardingAgent that OAuth authentication is complete.

    This function invokes the OnboardingAgent to continue the onboarding process
    after the user has successfully authenticated with Yahoo.

    Args:
        user_email: Email address of the user who just completed OAuth
    """
    from agent.AgentGraph import AgentState
    from agent.OnboardingAgent import agent

    logger = get_logger(__name__)

    try:
        from langchain_core.runnables import RunnableConfig

        logger.info(f"Notifying OnboardingAgent for user {user_email}...")
        config: RunnableConfig = {"configurable": {"thread_id": user_email}}

        # Send a message to the agent indicating OAuth is complete
        initial_state: AgentState = {
            "persona": "Gordie",
            "user_email": user_email,
            "game_key": None,
            "league_id": None,
            "team_id": None,
            "thread_id": user_email,
            "messages": [{"role": "user", "content": "I've completed the OAuth authentication!"}],
            "has_teams": False,
            "user_teams": [],
            "team_inference": None,
            "needs_clarification": False,
            "response": None,
            "route_to": None,
            "agent_flow": [],
            "current_agent_index": 0,
            "flow_complete": False,
            "flow_reasoning": None,
        }

        response = agent.invoke(initial_state, config=config)

        # Log the agent's response
        if response and "messages" in response:
            logger.info("OnboardingAgent response after OAuth:")
            for msg in response["messages"]:
                if hasattr(msg, "content"):
                    logger.info(msg.content)

    except Exception as e:
        logger.error(f"Failed to notify OnboardingAgent: {e}")
        # Don't raise - OAuth was successful, agent notification is secondary


def load_tokens_from_db(user_email: str) -> dict[str, Any] | None:
    """
    Load OAuth tokens from database.

    Args:
        user_email: Email address of the user

    Returns:
        dict with token data if found, None otherwise
    """
    conn = get_platform_db_connection()
    try:
        result = conn.execute(
            """
            SELECT access_token, refresh_token, token_time, token_type
            FROM yahoo_tokens
            WHERE user_email = ?
        """,
            (user_email,),
        ).fetchone()

        if not result:
            return None

        return {
            "access_token": result[0],
            "refresh_token": result[1],
            "token_time": result[2],
            "token_type": result[3],
        }
    finally:
        conn.close()


def get_oauth_nonce(user_email: str) -> str | None:
    """
    Retrieve stored OAuth nonce for a user.

    Args:
        user_email: Email address of the user

    Returns:
        The nonce string if found, None otherwise
    """
    conn = get_platform_db_connection()
    try:
        result = conn.execute(
            """
            SELECT nonce FROM oauth_nonces WHERE user_email = ?
        """,
            (user_email,),
        ).fetchone()

        return result[0] if result else None
    finally:
        conn.close()


def delete_oauth_nonce(user_email: str) -> None:
    """
    Delete OAuth nonce after use.

    Args:
        user_email: Email address of the user
    """
    conn = get_platform_db_connection()
    try:
        _ = conn.execute(
            """
            DELETE FROM oauth_nonces WHERE user_email = ?
        """,
            (user_email,),
        )
        _ = conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
