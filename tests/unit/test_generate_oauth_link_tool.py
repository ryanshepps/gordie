"""Tests for the Yahoo OAuth link generation tool."""

from collections.abc import Callable
from typing import cast

from pytest import MonkeyPatch

from tools.oauth.generate_oauth_link import generate_oauth_link


def test_generate_oauth_link_requires_public_https_base_url(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-1")
    monkeypatch.setenv("OAUTH_BASE_URL", "http://localhost:8000")

    run_tool = cast(
        Callable[[str, str], str],
        generate_oauth_link.func,  # pyright: ignore[reportAttributeAccessIssue]
    )
    result = run_tool("user@example.com", "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")

    assert result == (
        "OAuth configuration error: OAUTH_BASE_URL must be a public HTTPS URL. "
        "Please contact support."
    )
