"""Tool to generate Yahoo OAuth link for user authentication."""

import os
import secrets
from urllib.parse import urlencode

from langchain.tools import tool  # pyright: ignore[reportUnknownVariableType]
from pydantic import BaseModel, Field

from data.models import Medium
from data.pending_oauth_repository import PendingOAuthRepository
from module.logger import get_logger
from server.oauth_config import OAuthConfigurationError, get_oauth_base_url

logger = get_logger(__name__)


class GenerateOAuthLinkInput(BaseModel):
    external_id: str = Field(description="Medium-native identifier to resume after OAuth")
    thread_id: str = Field(description="Thread ID to resume after OAuth completes")
    channel: Medium = Field(
        default=Medium.EMAIL,
        description="Channel type: email, sms, telegram, or discord",
    )


@tool(args_schema=GenerateOAuthLinkInput)
def generate_oauth_link(
    external_id: str,
    thread_id: str,
    channel: Medium | str = Medium.EMAIL,
) -> str:
    """
    Generate a Yahoo OAuth authorization link for the user to authenticate.

    This tool creates a unique OAuth URL that the user should click to authorize
    the application to access their Yahoo Fantasy account.

    Args:
        external_id: Medium-native identifier to track the OAuth flow
        thread_id: Thread ID to resume after OAuth completes
        channel: Channel medium

    Returns:
        The OAuth authorization URL as a string, or an error message if configuration is missing.
    """
    client_id = os.getenv("YAHOO_CLIENT_ID")

    if not client_id:
        error_msg = "OAuth configuration error: YAHOO_CLIENT_ID not found. Please contact support."
        logger.error(error_msg)
        return error_msg
    try:
        oauth_base_url = get_oauth_base_url()
    except OAuthConfigurationError as exc:
        error_msg = f"OAuth configuration error: {exc}. Please contact support."
        logger.error(error_msg)
        return error_msg

    nonce = secrets.token_urlsafe(32)

    # Store pending OAuth record and get UUID for state param
    repo = PendingOAuthRepository()
    try:
        pending_id = repo.create(
            nonce=nonce,
            thread_id=thread_id,
            medium=channel if isinstance(channel, Medium) else Medium(channel),
            external_id=external_id,
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

    logger.info(f"Generated OAuth link for {channel}:{external_id} with state={pending_id}")

    return auth_url
