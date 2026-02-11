"""Tool to generate Yahoo OAuth link for user authentication."""

import os
import secrets
from urllib.parse import urlencode

from langchain.tools import tool
from pydantic import BaseModel, Field

from data.pending_oauth_repository import PendingOAuthRepository
from module.logger import get_logger

logger = get_logger(__name__)


class GenerateOAuthLinkInput(BaseModel):
    user_email: str = Field(description="User's email address to associate with the OAuth flow")
    thread_id: str = Field(description="Thread ID to resume after OAuth completes")
    channel: str = Field(default="email", description="Channel type: email, sms, or web")


@tool(args_schema=GenerateOAuthLinkInput)
def generate_oauth_link(user_email: str, thread_id: str, channel: str = "email") -> str:
    """
    Generate a Yahoo OAuth authorization link for the user to authenticate.

    This tool creates a unique OAuth URL that the user should click to authorize
    the application to access their Yahoo Fantasy account.

    Args:
        user_email: User's email address to track the OAuth flow
        thread_id: Thread ID to resume after OAuth completes
        channel: Channel type (email, sms, or web)

    Returns:
        The OAuth authorization URL as a string, or an error message if configuration is missing.
    """
    client_id = os.getenv("YAHOO_CLIENT_ID")
    oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")

    if not client_id:
        error_msg = "OAuth configuration error: YAHOO_CLIENT_ID not found. Please contact support."
        logger.error(error_msg)
        return error_msg

    nonce = secrets.token_urlsafe(32)

    # Store pending OAuth record and get UUID for state param
    repo = PendingOAuthRepository()
    try:
        pending_id = repo.create(
            nonce=nonce,
            thread_id=thread_id,
            channel=channel,
            user_email=user_email,
        )
    finally:
        repo.close()

    callback_url = f"{oauth_base_url.rstrip('/')}/callback"

    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email fspt-r",
        "nonce": nonce,
        "state": pending_id,
        "language": "en-us",
    }

    auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"

    logger.info(f"Generated OAuth link for user {user_email} with state={pending_id}")

    return auth_url
