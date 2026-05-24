"""Tests for shared Discord inbound message processing."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import UUID

from data.models import Medium
from server.discord_message_processor import process_discord_message


def _repo_mock() -> MagicMock:
    repo = MagicMock()
    repo.close.return_value = None
    return repo


def test_gateway_mode_sends_returned_agent_text(monkeypatch) -> None:
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    thread_id = "8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
    user_repo = _repo_mock()
    user_repo.resolve_user_id.return_value = user_id
    user_repo.get_identity_external_id.return_value = "user@test.com"
    thread_repo = _repo_mock()
    thread_repo.resolve.return_value = MagicMock(thread_id=thread_id)
    processed_repo = _repo_mock()
    processed_repo.claim.return_value = True
    gateway = MagicMock()
    gateway.check_question_allowed.return_value = (True, "")
    message_agent = MagicMock(return_value="Go with Matthews tonight.")
    message_agent_module = ModuleType("scripts.message_agent")
    message_agent_module.__dict__["message_agent"] = message_agent
    monkeypatch.setitem(sys.modules, "scripts.message_agent", message_agent_module)
    send_text = MagicMock()

    with (
        patch("data.user_repository.UserRepository", return_value=user_repo),
        patch("data.thread_repository.ThreadRepository", return_value=thread_repo),
        patch(
            "data.processed_inbound_message_repository.ProcessedInboundMessageRepository",
            return_value=processed_repo,
        ),
        patch("billing.get_gateway", return_value=gateway),
    ):
        result = process_discord_message(
            discord_user_id="discord-user-1",
            display_name="ryan",
            message_body="Who should I start?",
            inbound_message_id="message-1",
            send_text=send_text,
            logger=MagicMock(),
        )

    assert result.status == "processed"
    assert result.thread_id == thread_id
    send_text.assert_called_once_with(thread_id, "Go with Matthews tonight.")
    message_agent.assert_called_once()
    assert message_agent.call_args.kwargs["channel"] is Medium.DISCORD


def test_duplicate_message_skips_agent(monkeypatch) -> None:
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    thread_id = "8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
    user_repo = _repo_mock()
    user_repo.resolve_user_id.return_value = user_id
    user_repo.get_identity_external_id.return_value = "user@test.com"
    thread_repo = _repo_mock()
    thread_repo.resolve.return_value = MagicMock(thread_id=thread_id)
    processed_repo = _repo_mock()
    processed_repo.claim.return_value = False
    message_agent = MagicMock()
    message_agent_module = ModuleType("scripts.message_agent")
    message_agent_module.__dict__["message_agent"] = message_agent
    monkeypatch.setitem(sys.modules, "scripts.message_agent", message_agent_module)

    with (
        patch("data.user_repository.UserRepository", return_value=user_repo),
        patch("data.thread_repository.ThreadRepository", return_value=thread_repo),
        patch(
            "data.processed_inbound_message_repository.ProcessedInboundMessageRepository",
            return_value=processed_repo,
        ),
    ):
        result = process_discord_message(
            discord_user_id="discord-user-1",
            display_name="ryan",
            message_body="Who should I start?",
            inbound_message_id="message-1",
            send_text=MagicMock(),
            logger=MagicMock(),
        )

    assert result.status == "duplicate"
    message_agent.assert_not_called()
