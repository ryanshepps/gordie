"""Integration-style tests for Discord HTTP interactions."""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from nacl.signing import SigningKey


@pytest.fixture
def signing_key(monkeypatch) -> SigningKey:
    key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", key.verify_key.encode().hex())
    monkeypatch.delenv("DISCORD_APPLICATION_ID", raising=False)
    return key


@pytest.fixture
def app(signing_key):
    from quart import Quart

    from server.routes.discord_routes import register_discord_routes

    app = Quart(__name__)
    register_discord_routes(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _headers(signing_key: SigningKey, body: bytes, timestamp: str = "1700000000") -> dict[str, str]:
    signature = signing_key.sign(timestamp.encode("utf-8") + body).signature.hex()
    return {
        "Content-Type": "application/json",
        "X-Signature-Ed25519": signature,
        "X-Signature-Timestamp": timestamp,
    }


def _command_payload() -> dict[str, object]:
    return {
        "id": "interaction-1",
        "type": 2,
        "application_id": "app-1",
        "token": "token-1",
        "data": {
            "name": "gordie",
            "options": [{"name": "question", "value": "Who should I start?"}],
        },
        "member": {"user": {"id": "discord-user-1", "username": "ryan"}},
    }


class TestDiscordInteractions:
    async def test_ping_returns_pong(self, client, signing_key) -> None:
        body = json.dumps({"type": 1}).encode()

        response = await client.post(
            "/discord/interactions",
            data=body,
            headers=_headers(signing_key, body),
        )

        assert response.status_code == 200
        assert await response.get_json() == {"type": 1}

    async def test_invalid_signature_returns_401(self, client, signing_key) -> None:
        body = json.dumps({"type": 1}).encode()
        other_key = SigningKey.generate()

        response = await client.post(
            "/discord/interactions",
            data=body,
            headers=_headers(other_key, body),
        )

        assert response.status_code == 401

    async def test_gordie_command_returns_deferred_ack(self, client, signing_key) -> None:
        body = json.dumps(_command_payload()).encode()

        with patch("server.routes.discord_routes.threading.Thread") as thread_cls:
            response = await client.post(
                "/discord/interactions",
                data=body,
                headers=_headers(signing_key, body),
            )

        assert response.status_code == 200
        assert await response.get_json() == {"type": 5}
        thread_cls.assert_called_once()
        thread_cls.return_value.start.assert_called_once()


def _repo_mock() -> MagicMock:
    repo = MagicMock()
    repo.close.return_value = None
    return repo


class TestProcessDiscordInteraction:
    def test_known_user_invokes_message_agent(self, monkeypatch) -> None:
        from server.routes.discord_routes import _process_discord_interaction

        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        thread_id = "8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
        user_repo = _repo_mock()
        user_repo.resolve_user_id.return_value = user_id
        user_repo.get_identity_external_id.return_value = "user@test.com"
        thread_repo = _repo_mock()
        thread_repo.resolve.return_value = MagicMock(thread_id=thread_id)
        target_repo = _repo_mock()
        processed_repo = _repo_mock()
        processed_repo.claim.return_value = True
        gateway = MagicMock()
        gateway.check_question_allowed.return_value = (True, "")
        message_agent = MagicMock()
        message_agent_module = ModuleType("scripts.message_agent")
        message_agent_module.__dict__["message_agent"] = message_agent
        monkeypatch.setitem(sys.modules, "scripts.message_agent", message_agent_module)

        with (
            patch("data.user_repository.UserRepository", return_value=user_repo),
            patch("data.thread_repository.ThreadRepository", return_value=thread_repo),
            patch(
                "data.discord_interaction_repository.DiscordInteractionRepository",
                return_value=target_repo,
            ),
            patch(
                "data.processed_inbound_message_repository.ProcessedInboundMessageRepository",
                return_value=processed_repo,
            ),
            patch("billing.get_gateway", return_value=gateway),
        ):
            _process_discord_interaction(
                application_id="app-1",
                interaction_token="token-1",
                interaction_id="interaction-1",
                discord_user_id="discord-user-1",
                display_name="ryan",
                message_body="Who should I start?",
                logger=MagicMock(),
            )

        target_repo.upsert_target.assert_called_once_with(thread_id, "app-1", "token-1")
        processed_repo.claim.assert_called_once()
        message_agent.assert_called_once()
        from data.models import Medium

        assert message_agent.call_args.kwargs["channel"] is Medium.DISCORD
        assert message_agent.call_args.kwargs["thread_id"] == thread_id
        assert message_agent.call_args.kwargs["user_id"] == str(user_id)
        assert message_agent.call_args.kwargs["external_id"] == "discord-user-1"

    def test_unknown_user_receives_oauth_link(self) -> None:
        from server.routes.discord_routes import _process_discord_interaction

        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        thread_id = "8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
        user_repo = _repo_mock()
        user_repo.resolve_user_id.return_value = user_id
        user_repo.get_identity_external_id.return_value = None
        thread_repo = _repo_mock()
        thread_repo.resolve.return_value = MagicMock(thread_id=thread_id)
        target_repo = _repo_mock()
        processed_repo = _repo_mock()
        processed_repo.claim.return_value = True

        with (
            patch("data.user_repository.UserRepository", return_value=user_repo),
            patch("data.thread_repository.ThreadRepository", return_value=thread_repo),
            patch(
                "data.discord_interaction_repository.DiscordInteractionRepository",
                return_value=target_repo,
            ),
            patch(
                "data.processed_inbound_message_repository.ProcessedInboundMessageRepository",
                return_value=processed_repo,
            ),
            patch(
                "server.oauth_link_service.generate_cold_start_oauth_link",
                return_value="https://oauth.example",
            ),
            patch("server.adapters.discord_adapter.send_discord_text") as send_discord_text,
        ):
            _process_discord_interaction(
                application_id="app-1",
                interaction_token="token-1",
                interaction_id="interaction-1",
                discord_user_id="discord-user-1",
                display_name="ryan",
                message_body="Who should I start?",
                logger=MagicMock(),
            )

        send_discord_text.assert_called_once()
        assert send_discord_text.call_args.args[0] == thread_id
        assert "https://oauth.example" in send_discord_text.call_args.args[1]

    def test_duplicate_interaction_does_not_invoke_agent(self, monkeypatch) -> None:
        from server.routes.discord_routes import _process_discord_interaction

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
                "data.discord_interaction_repository.DiscordInteractionRepository",
                return_value=_repo_mock(),
            ),
            patch(
                "data.processed_inbound_message_repository.ProcessedInboundMessageRepository",
                return_value=processed_repo,
            ),
        ):
            _process_discord_interaction(
                application_id="app-1",
                interaction_token="token-1",
                interaction_id="interaction-1",
                discord_user_id="discord-user-1",
                display_name="ryan",
                message_body="Who should I start?",
                logger=MagicMock(),
            )

        message_agent.assert_not_called()
