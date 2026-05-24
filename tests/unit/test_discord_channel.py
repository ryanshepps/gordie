"""Tests for Discord adapter dispatch."""

from unittest.mock import MagicMock, patch

from agent.agent_state import AgentState
from server.adapters.discord_adapter import DiscordAdapter


def test_discord_adapter_edits_latest_interaction_target() -> None:
    state: AgentState = {
        "messages": [],
        "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
    }
    target = MagicMock(application_id="app-1", interaction_token="token-1")
    result = MagicMock(success=True)
    service = MagicMock()
    service.edit_original_response.return_value = result

    with (
        patch("data.discord_interaction_repository.DiscordInteractionRepository") as repo_cls,
        patch("server.discord_service.DiscordService", return_value=service),
    ):
        repo_cls.return_value.get_target.return_value = target
        DiscordAdapter().send("discord-user-1", "Go with Matthews tonight.", state)

    service.edit_original_response.assert_called_once_with(
        "app-1",
        "token-1",
        "Go with Matthews tonight.",
    )


def test_discord_adapter_skips_when_thread_id_missing() -> None:
    state: AgentState = {"messages": []}

    with patch("server.discord_service.DiscordService") as service_cls:
        DiscordAdapter().send("discord-user-1", "Hello", state)

    service_cls.assert_not_called()


def test_discord_adapter_skips_when_target_missing() -> None:
    state: AgentState = {
        "messages": [],
        "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
    }

    with (
        patch("data.discord_interaction_repository.DiscordInteractionRepository") as repo_cls,
        patch("server.discord_service.DiscordService") as service_cls,
    ):
        repo_cls.return_value.get_target.return_value = None
        DiscordAdapter().send("discord-user-1", "Hello", state)

    service_cls.assert_not_called()
