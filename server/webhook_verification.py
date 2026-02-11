"""
Webhook verification utilities for Mailgun and Sinch webhooks.

This module provides security functions to verify webhook authenticity
and prevent replay attacks.
"""

import hashlib
import hmac
import os
import time

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


def verify_sinch_webhook(raw_body: bytes, signature: str) -> bool:
    """Verify Sinch webhook signature using HMAC-SHA256.

    Args:
        raw_body: Raw request body bytes
        signature: Signature from x-sinch-webhook-signature header

    Returns:
        True if signature is valid, False otherwise
    """
    webhook_secret = os.getenv("SINCH_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.error("SINCH_WEBHOOK_SECRET not configured")
        return False

    hmac_digest = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, hmac_digest)
