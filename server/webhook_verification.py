"""
Webhook verification utilities for Mailgun and Sinch webhooks.

This module provides security functions to verify webhook authenticity
and prevent replay attacks.
"""

import hashlib
import hmac
import os
import time

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from module.logger import get_logger

logger = get_logger(__name__)


def verify_mailgun_webhook(token: str, timestamp: str, signature: str) -> bool:
    """
    Verify Mailgun webhook signature using HMAC-SHA256.

    Args:
        token: Random token from webhook
        timestamp: Unix timestamp from webhook
        signature: HMAC signature from webhook

    Returns:
        True if signature is valid, False otherwise
    """
    signing_key = os.getenv("MAILGUN_WEBHOOK_SIGNING_KEY")
    if not signing_key:
        logger.error("MAILGUN_WEBHOOK_SIGNING_KEY not configured")
        return False

    # Concatenate timestamp and token
    message = f"{timestamp}{token}"

    # Generate HMAC-SHA256
    hmac_digest = hmac.new(
        key=signing_key.encode("utf-8"), msg=message.encode("utf-8"), digestmod=hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, hmac_digest)


def is_timestamp_fresh(timestamp: str, max_age_seconds: int = 300) -> bool:
    """
    Ensure webhook timestamp is within acceptable window (default 5 minutes).

    This prevents replay attacks by rejecting old or future-dated requests.

    Args:
        timestamp: Unix timestamp as string
        max_age_seconds: Maximum age in seconds (default 300 = 5 minutes)

    Returns:
        True if timestamp is within acceptable range, False otherwise
    """
    try:
        webhook_time = int(timestamp)
        current_time = int(time.time())
        time_diff = abs(current_time - webhook_time)

        if time_diff > max_age_seconds:
            logger.warning(f"Timestamp too old or in future: {time_diff}s difference")
            return False

        return True
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid timestamp format: {timestamp} - {e}")
        return False


def verify_sinch_webhook_token(token: str) -> bool:
    """Verify Sinch webhook auth token passed as a query parameter.

    Sinch callback URLs can include query parameters. We append
    ``?auth_token=<secret>`` to the URL configured in the Sinch
    dashboard so the token survives proxies (e.g. Cloudflare Tunnel)
    that strip the Authorization header.

    Args:
        token: The ``auth_token`` query parameter value from the request

    Returns:
        True if the token matches the expected secret, False otherwise
    """
    expected = os.getenv("SINCH_WEBHOOK_TOKEN")
    if not expected:
        logger.error("SINCH_WEBHOOK_TOKEN not configured")
        return False

    return hmac.compare_digest(token, expected)


def verify_discord_interaction(signature: str, timestamp: str, body: bytes) -> bool:
    """Verify a Discord interaction Ed25519 signature.

    Discord signs the exact timestamp bytes followed by the exact raw request
    body bytes. Do not parse or reserialize the body before verification.
    """
    public_key = os.getenv("DISCORD_PUBLIC_KEY")
    if not public_key:
        logger.error("DISCORD_PUBLIC_KEY not configured")
        return False

    if not is_timestamp_fresh(timestamp):
        return False

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        _ = verify_key.verify(timestamp.encode("utf-8") + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError) as exc:
        logger.warning(f"Invalid Discord interaction signature: {exc}")
        return False
