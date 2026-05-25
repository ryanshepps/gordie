"""OAuth runtime configuration helpers."""

import os
from ipaddress import ip_address
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
    hostname = parsed.hostname
    if hostname is None or _is_private_hostname(hostname):
        raise OAuthConfigurationError("OAUTH_BASE_URL must be a public HTTPS URL")
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        msg = "OAUTH_BASE_URL must not include a path, query string, or fragment"
        raise OAuthConfigurationError(msg)
    return normalized


def _is_private_hostname(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized in {"localhost"} or normalized.endswith(".localhost"):
        return True

    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False

    return not parsed_ip.is_global
