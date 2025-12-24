"""
OAuth flow orchestration for Yahoo Fantasy API.

This module handles the complete OAuth flow including token exchange,
validation, storage, and related utilities.
"""

import base64
import json
import logging
import os
import secrets
import webbrowser
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv

from client.duck_db_client import get_platform_db_connection
from module.logger import get_logger

load_dotenv()


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
    # Import here to avoid circular imports
    from server.server import Server

    logger = get_logger(__name__, level=logging.DEBUG)

    client_id = os.getenv("YAHOO_CLIENT_ID")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET")
    oauth_base_url = os.getenv("OAUTH_BASE_URL")

    if not client_id or not client_secret:
        raise ValueError("Missing YAHOO_CLIENT_ID and/or YAHOO_CLIENT_SECRET in .env")

    logger.info(f"Starting OAuth flow for user: {user_email}")
    server = Server(host="localhost", port=8000)

    try:
        server.start()
        callback_url = server.get_callback_url(oauth_base_url or "http://localhost:8000")
        logger.info(f"Callback URL: {callback_url}")

        nonce = secrets.token_urlsafe(32)
        auth_url = build_auth_url(
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

        token_data = exchange_code(auth_code, client_id, client_secret, callback_url, nonce)
        logger.info("✓ Access tokens received")

        yahoo_email = get_yahoo_email(token_data["access_token"])
        if not yahoo_email:
            raise RuntimeError("Could not retrieve Yahoo email")

        logger.info(f"✓ Yahoo email: {yahoo_email}")
        token_data["yahoo_email"] = yahoo_email

        save_tokens(user_email, yahoo_email, token_data)
        logger.info("✓ Tokens saved to database")

        # Notify the OnboardingAgent that OAuth is complete
        notify_onboarding_agent(user_email)

        logger.info(f"OAuth flow completed for {user_email}")
        return token_data

    finally:
        server.shutdown()


def build_auth_url(
    client_id: str, redirect_uri: str, scope: str, nonce: str, state: str | None = None
) -> str:
    """Build Yahoo OAuth authorization URL."""
    from urllib.parse import urlencode

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


def validate_nonce(id_token: str, expected_nonce: str) -> None:
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


def exchange_code(
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
            validate_nonce(token_response["id_token"], nonce)
            logger.info("✓ ID token nonce validated")

        return token_data

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Token exchange failed: {e}") from e


def get_yahoo_email(access_token: str) -> str | None:
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


def save_tokens(user_email: str, yahoo_email: str, token_data: dict[str, Any]) -> None:
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


def notify_onboarding_agent(user_email: str, thread_id: str | None = None) -> None:
    """
    Notify the OnboardingAgent that OAuth authentication is complete.

    This function invokes the OnboardingAgent to continue the onboarding process
    after the user has successfully authenticated with Yahoo.

    Args:
        user_email: Email address of the user who just completed OAuth
        thread_id: Optional thread ID to resume the correct conversation
    """
    from agent.agent_state import AgentState
    from agent.graph_builder import agent

    logger = get_logger(__name__)

    try:
        from langchain_core.runnables import RunnableConfig

        # Use provided thread_id or fallback to user_email for backwards compatibility
        active_thread_id = thread_id if thread_id else user_email

        logger.info(f"Notifying OnboardingAgent for user {user_email} (thread: {active_thread_id})...")
        config: RunnableConfig = {"configurable": {"thread_id": active_thread_id}}

        # Send a message to the agent indicating OAuth is complete
        initial_state: AgentState = {
            "user_email": user_email,
            "league_id": None,
            "team_id": None,
            "thread_id": active_thread_id,
            "messages": [{"role": "user", "content": "I've completed the OAuth authentication!"}],
            "user_teams": [],
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
