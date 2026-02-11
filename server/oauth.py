"""
OAuth utilities for Yahoo Fantasy API.

This module provides token exchange, validation, and related utilities
used by the OAuth callback handler.
"""

import base64
import json
from datetime import datetime
from typing import Any

import requests

from module.logger import get_logger


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
            logger.info("ID token nonce validated")

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
