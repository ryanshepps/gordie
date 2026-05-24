"""Build Yahoo OAuth links for channel cold-start onboarding."""

import os
import secrets
from urllib.parse import urlencode

from data.models import Medium
from data.pending_oauth_repository import PendingOAuthRepository
from module.logger import get_logger
from server.oauth_config import OAuthConfigurationError, get_oauth_base_url

logger = get_logger(__name__)


def generate_cold_start_oauth_link(
    medium: Medium,
    external_id: str,
    thread_id: str,
) -> str:
    """Create a pending OAuth record and return a Yahoo authorization URL."""
    client_id = os.getenv("YAHOO_CLIENT_ID")

    if not client_id:
        logger.error("YAHOO_CLIENT_ID not set, cannot generate cold-start OAuth link")
        raise ValueError("OAuth not configured")
    try:
        oauth_base_url = get_oauth_base_url()
    except OAuthConfigurationError as exc:
        logger.error(f"{exc}, cannot generate cold-start OAuth link")
        raise ValueError("OAuth not configured") from exc

    nonce = secrets.token_urlsafe(32)

    repo = PendingOAuthRepository()
    try:
        pending_id = repo.create(
            nonce=nonce,
            thread_id=thread_id,
            medium=medium,
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
    logger.info(f"Generated cold-start OAuth link for {medium.value}:{external_id}")
    return auth_url
