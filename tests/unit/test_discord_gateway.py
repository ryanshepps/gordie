"""Tests for Discord Gateway local bot helpers."""

import pytest

from server.discord_gateway import (
    DISCORD_MODE_GATEWAY,
    discord_gateway_enabled,
    extract_gateway_message_body,
    load_gateway_config,
    parse_allowed_user_ids,
)


def test_parse_allowed_user_ids_deduplicates_values() -> None:
    assert parse_allowed_user_ids("123, 456,123,, ") == ("123", "456")


def test_extract_gateway_message_body_allows_direct_messages_without_mention() -> None:
    body = extract_gateway_message_body(
        "Who should I start?",
        bot_user_id="999",
        require_mention=True,
        is_direct_message=True,
    )

    assert body == "Who should I start?"


def test_extract_gateway_message_body_requires_mention_in_servers() -> None:
    without_mention = extract_gateway_message_body(
        "Who should I start?",
        bot_user_id="999",
        require_mention=True,
        is_direct_message=False,
    )
    with_mention = extract_gateway_message_body(
        "<@999> Who should I start?",
        bot_user_id="999",
        require_mention=True,
        is_direct_message=False,
    )

    assert without_mention is None
    assert with_mention == "Who should I start?"


def test_extract_gateway_message_body_can_disable_server_mention_requirement() -> None:
    body = extract_gateway_message_body(
        "Who should I start?",
        bot_user_id=None,
        require_mention=False,
        is_direct_message=False,
    )

    assert body == "Who should I start?"


def test_gateway_enabled_by_discord_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_MODE", DISCORD_MODE_GATEWAY)
    monkeypatch.setenv("CHAT_MEDIA", "discord")

    assert discord_gateway_enabled()


def test_gateway_disabled_when_discord_chat_media_not_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_MODE", DISCORD_MODE_GATEWAY)
    monkeypatch.setenv("CHAT_MEDIA", "email")

    assert not discord_gateway_enabled()


def test_load_gateway_config_requires_allowed_user_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_MODE", DISCORD_MODE_GATEWAY)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.delenv("DISCORD_ALLOWED_USER_IDS", raising=False)

    with pytest.raises(ValueError, match="DISCORD_ALLOWED_USER_IDS"):
        _ = load_gateway_config()
