"""Dev-only CLI script for generating an OAuth URL."""

import os
import secrets

from dotenv import load_dotenv

from module.logger import get_logger
from server.oauth import build_auth_url

load_dotenv()

logger = get_logger(__name__)


def main():
    client_id = os.getenv("YAHOO_CLIENT_ID")
    oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")

    if not client_id:
        logger.error("YAHOO_CLIENT_ID not set")
        return

    callback_url = f"{oauth_base_url.rstrip('/')}/callback"
    nonce = secrets.token_urlsafe(32)
    auth_url = build_auth_url(client_id, callback_url, "openid email fspt-r", nonce)

    print(f"OAuth URL:\n{auth_url}")


if __name__ == "__main__":
    main()
