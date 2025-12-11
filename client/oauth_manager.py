"""Yahoo Fantasy OAuth flow manager with embedded callback server."""

import webbrowser
import requests
import os
import secrets
import threading
import base64
import json
from typing import Optional
from urllib.parse import urlencode
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging

from client.DuckDbClient import get_platform_db_connection
from module.logger import get_logger

load_dotenv()
logger = get_logger(__name__, level=logging.DEBUG)

# Suppress Flask logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)


class _CallbackServer:
    """Local Flask server for OAuth callbacks."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.server_thread: Optional[threading.Thread] = None
        self.auth_code: Optional[str] = None
        self.auth_error: Optional[str] = None
        self.code_received = threading.Event()
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/callback')
        def callback():
            code = request.args.get('code')
            error = request.args.get('error')
            error_description = request.args.get('error_description')

            if error:
                self.auth_error = error
                logger.error(f"OAuth Error: {error}")
                if error_description:
                    logger.error(f"Error Description: {error_description}")
                self.code_received.set()
                return f"<html><body><h1>Authentication Error</h1><p>{error}: {error_description or 'No description'}</p></body></html>", 400

            if code:
                self.auth_code = code
                self.code_received.set()
                return "<html><body><h1>Authentication Successful!</h1><p>You can close this window.</p></body></html>"

            return "<html><body><h1>Invalid Request</h1><p>No authorization code received.</p></body></html>", 400

        @self.app.route('/health')
        def health():
            return jsonify({"status": "ok"})

    def start(self):
        def run_server():
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        import time
        time.sleep(1)

    def wait_for_code(self, timeout: Optional[float] = 300) -> Optional[str]:
        if not self.code_received.wait(timeout=timeout):
            return None
        if self.auth_error:
            raise RuntimeError(f"OAuth error: {self.auth_error}")
        return self.auth_code

    def shutdown(self):
        self.auth_code = None
        self.auth_error = None
        self.code_received.clear()

    def get_callback_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/callback"


def initiate_oauth_flow(user_email: str) -> dict:
    """
    Complete OAuth flow: start server, authorize, exchange tokens, save to DB.
    
    Returns: dict with access_token, refresh_token, token_time, token_type
    """
    client_id = os.getenv("YAHOO_CLIENT_ID")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET")
    oauth_base_url = os.getenv("OAUTH_BASE_URL")

    if not client_id or not client_secret:
        raise ValueError("Missing YAHOO_CLIENT_ID and/or YAHOO_CLIENT_SECRET in .env")

    logger.info(f"Starting OAuth flow for user: {user_email}")
    server = _CallbackServer(host="localhost", port=8000)

    try:
        server.start()
        callback_url = server.get_callback_url(oauth_base_url or "http://localhost:8000")
        logger.info(f"Callback URL: {callback_url}")

        nonce = secrets.token_urlsafe(32)
        auth_url = _build_auth_url(client_id, callback_url, "openid email fspt-r", nonce)

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

        logger.info(f"OAuth flow completed for {user_email}")
        return token_data

    finally:
        server.shutdown()


def _build_auth_url(client_id: str, redirect_uri: str, scope: str, nonce: str) -> str:
    """Build Yahoo OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "nonce": nonce,
        "language": "en-us"
    }
    return f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"


def _validate_nonce(id_token: str, expected_nonce: str) -> None:
    """Validate nonce in ID token."""
    parts = id_token.split('.')
    if len(parts) != 3:
        raise RuntimeError("Invalid ID token format")

    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding

    claims = json.loads(base64.urlsafe_b64decode(payload))
    token_nonce = claims.get("nonce")

    if token_nonce and token_nonce != expected_nonce:
        raise RuntimeError("Nonce validation failed")

    logger.debug("Nonce validated")


def _exchange_code(auth_code: str, client_id: str, client_secret: str, 
                   redirect_uri: str, nonce: str) -> dict:
    """Exchange authorization code for tokens."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri
    }

    try:
        response = requests.post(
            "https://api.login.yahoo.com/oauth2/get_token",
            headers=headers,
            data=data,
            timeout=10
        )
        response.raise_for_status()
        token_response = response.json()

        token_data = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response["refresh_token"],
            "token_time": datetime.now(),
            "token_type": token_response.get("token_type", "Bearer")
        }

        if "id_token" in token_response:
            token_data["id_token"] = token_response["id_token"]
            _validate_nonce(token_response["id_token"], nonce)
            logger.info("✓ ID token nonce validated")

        return token_data

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Token exchange failed: {e}") from e


def _get_yahoo_email(access_token: str) -> Optional[str]:
    """Fetch Yahoo user email from userinfo endpoint."""
    try:
        response = requests.get(
            "https://api.login.yahoo.com/openid/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("email")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch userinfo: {e}")
        return None


def _save_tokens(user_email: str, yahoo_email: str, token_data: dict) -> None:
    """Save OAuth tokens to database."""
    conn = get_platform_db_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO yahoo_tokens (
                user_email, yahoo_email, access_token, refresh_token, 
                token_time, token_type, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_email, yahoo_email, token_data["access_token"],
            token_data["refresh_token"], token_data["token_time"],
            token_data["token_type"]
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to save tokens: {e}") from e
    finally:
        conn.close()


def load_tokens_from_db(user_email: str) -> Optional[dict]:
    """Load OAuth tokens from database."""
    conn = get_platform_db_connection()
    try:
        result = conn.execute("""
            SELECT access_token, refresh_token, token_time, token_type
            FROM yahoo_tokens
            WHERE user_email = ?
        """, (user_email,)).fetchone()

        if not result:
            return None

        return {
            "access_token": result[0],
            "refresh_token": result[1],
            "token_time": result[2],
            "token_type": result[3]
        }
    finally:
        conn.close()
