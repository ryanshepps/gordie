"""Tests for Discord outbound service."""

from collections.abc import Mapping
from typing import cast
from unittest.mock import patch

import requests

from server.discord_service import DISCORD_MAX_CONTENT_LENGTH, DiscordService


class FakeDiscordResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code: int = status_code
        self.text: str = text
        self.raise_for_status_called: bool = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True


def test_edit_original_response_patches_discord_webhook() -> None:
    response = FakeDiscordResponse(status_code=200)

    with patch("server.discord_service.requests.patch", return_value=response) as mock_patch:
        result = DiscordService().edit_original_response("app-1", "token-1", "Hello")

    assert result.success is True
    mock_patch.assert_called_once_with(
        "https://discord.com/api/webhooks/app-1/token-1/messages/@original",
        json={"content": "Hello", "allowed_mentions": {"parse": []}},
        timeout=10,
    )


def test_edit_original_response_truncates_overlong_content() -> None:
    response = FakeDiscordResponse(status_code=200)
    long_content = "x" * (DISCORD_MAX_CONTENT_LENGTH + 1)

    with patch("server.discord_service.requests.patch", return_value=response) as mock_patch:
        result = DiscordService().edit_original_response("app-1", "token-1", long_content)

    assert result.success is True
    payload = cast(Mapping[str, object], mock_patch.call_args.kwargs["json"])
    content = cast(str, payload["content"])
    assert len(content) == DISCORD_MAX_CONTENT_LENGTH
    assert "Response truncated for Discord" in content
    assert payload["allowed_mentions"] == {"parse": []}


def test_edit_original_response_returns_error_for_4xx() -> None:
    response = FakeDiscordResponse(status_code=404, text="not found")

    with patch("server.discord_service.requests.patch", return_value=response):
        result = DiscordService().edit_original_response("app-1", "token-1", "Hello")

    assert result.success is False
    assert result.error == "Client error: 404"
    assert response.raise_for_status_called is False


def test_edit_original_response_returns_error_for_timeout() -> None:
    with patch(
        "server.discord_service.requests.patch",
        side_effect=requests.exceptions.Timeout("too slow"),
    ):
        result = DiscordService().edit_original_response("app-1", "token-1", "Hello")

    assert result.success is False
    assert "too slow" in str(result.error)
