"""Tool to generate Yahoo OAuth link for user authentication."""

import os
import secrets
from urllib.parse import urlencode

from langchain.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import text

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


class GenerateOAuthLinkInput(BaseModel):
    user_email: str = Field(description="User's email address to associate with the OAuth flow")
    thread_id: str = Field(description="Thread ID to resume after OAuth completes")


@tool(args_schema=GenerateOAuthLinkInput)
def generate_oauth_link(user_email: str, thread_id: str) -> str:
    """
    Generate a Yahoo OAuth authorization link for the user to authenticate.

    This tool creates a unique OAuth URL that the user should click to authorize
    the application to access their Yahoo Fantasy account.

    Args:
        user_email: User's email address to track the OAuth flow
        thread_id: Thread ID to resume after OAuth completes

    Returns:
        The OAuth authorization URL as a string, or an error message if configuration is missing.
    """
    client_id = os.getenv("YAHOO_CLIENT_ID")
    oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")

    if not client_id:
        error_msg = "OAuth configuration error: YAHOO_CLIENT_ID not found. Please contact support."
        logger.error(error_msg)
        return error_msg

    # Generate a unique nonce for security
    nonce = secrets.token_urlsafe(32)

    # Store nonce and thread_id in database for later retrieval during callback
    _store_oauth_nonce(user_email, nonce, thread_id)

    # Build callback URL
    callback_url = f"{oauth_base_url.rstrip('/')}/callback"

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email fspt-r",  # openid, email, and fantasy sports read
        "nonce": nonce,
        "state": user_email,  # Pass user_email via state parameter
        "language": "en-us",
    }

    auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"

    logger.info(f"Generated OAuth link for user {user_email} with callback: {callback_url}")

    return auth_url


def _store_oauth_nonce(user_email: str, nonce: str, thread_id: str) -> None:
    """Store OAuth nonce and thread_id in database for later retrieval."""
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO oauth_nonces (user_email, nonce, thread_id, created_at)
                VALUES (:user_email, :nonce, :thread_id, CURRENT_TIMESTAMP)
                ON CONFLICT (user_email) DO UPDATE SET
                    nonce = EXCLUDED.nonce,
                    thread_id = EXCLUDED.thread_id,
                    created_at = CURRENT_TIMESTAMP
                """
            ),
            {"user_email": user_email, "nonce": nonce, "thread_id": thread_id},
        )
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to store OAuth nonce: {e}")
        raise
    finally:
        session.close()
