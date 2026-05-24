"""OAuth runtime configuration helpers."""

import os
from urllib.parse import urlparse


class OAuthConfigurationError(ValueError):
    """Raised when OAuth cannot be safely configured."""


def get_oauth_base_url() -> str:
    """Return the configured public HTTPS OAuth base URL."""
    value = os.getenv("OAUTH_BASE_URL")
    if value is None or not value.strip():
        raise OAuthConfigurationError("OAUTH_BASE_URL must be set")
    return normalize_oauth_base_url(value)


def normalize_oauth_base_url(value: str) -> str:
    """Normalize and validate a public HTTPS OAuth base URL."""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc:
        raise OAuthConfigurationError("OAUTH_BASE_URL must be a public HTTPS URL")
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        msg = "OAUTH_BASE_URL must not include a path, query string, or fragment"
        raise OAuthConfigurationError(msg)
    return normalized
