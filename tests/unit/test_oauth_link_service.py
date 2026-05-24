"""Tests for cold-start OAuth link generation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from pytest import MonkeyPatch

from data.models import Medium
from server.oauth_link_service import generate_cold_start_oauth_link


class FakePendingOAuthRepository:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str, Medium, str]] = []
        self.close_count: int = 0

    def create(
        self,
        nonce: str,
        thread_id: str,
        medium: Medium,
        external_id: str,
    ) -> str:
        self.create_calls.append((nonce, thread_id, medium, external_id))
        return "pending-1"

    def close(self) -> None:
        self.close_count += 1


def test_generate_cold_start_oauth_link_creates_pending_oauth(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-1")
    monkeypatch.setenv("OAUTH_BASE_URL", "https://gordie.example")

    repo = FakePendingOAuthRepository()

    with patch("server.oauth_link_service.PendingOAuthRepository", return_value=repo):
        url = generate_cold_start_oauth_link(
            Medium.DISCORD,
            "discord-user-1",
            "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        )

    assert len(repo.create_calls) == 1
    _, _, medium, external_id = repo.create_calls[0]
    assert medium is Medium.DISCORD
    assert external_id == "discord-user-1"
    assert repo.close_count == 1

    params = parse_qs(urlparse(url).query)
    assert params["client_id"] == ["client-1"]
    assert params["redirect_uri"] == ["https://gordie.example/callback"]
    assert params["state"] == ["pending-1"]


def test_generate_cold_start_oauth_link_requires_client_id(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("YAHOO_CLIENT_ID", raising=False)

    try:
        _ = generate_cold_start_oauth_link(
            Medium.SMS,
            "+15551234567",
            "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        )
    except ValueError as exc:
        assert str(exc) == "OAuth not configured"
    else:
        raise AssertionError("Expected OAuth configuration failure")


def test_generate_cold_start_oauth_link_requires_public_https_base_url(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-1")
    monkeypatch.setenv("OAUTH_BASE_URL", "http://localhost:8000")

    try:
        _ = generate_cold_start_oauth_link(
            Medium.SMS,
            "+15551234567",
            "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        )
    except ValueError as exc:
        assert str(exc) == "OAuth not configured"
    else:
        raise AssertionError("Expected OAuth configuration failure")


def test_generate_cold_start_oauth_link_rejects_localhost_base_url(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-1")
    monkeypatch.setenv("OAUTH_BASE_URL", "https://localhost:8000")

    try:
        _ = generate_cold_start_oauth_link(
            Medium.SMS,
            "+15551234567",
            "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        )
    except ValueError as exc:
        assert str(exc) == "OAuth not configured"
    else:
        raise AssertionError("Expected OAuth configuration failure")
