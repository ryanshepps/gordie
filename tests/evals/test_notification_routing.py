"""Routing tests for notification requests.

Verify the supervisor routes notification requests to the manage_notifications tool
with the correct arguments.

These tests do NOT require LLM evaluation - they verify deterministic tool routing.
"""

import uuid
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pytest_mock import MockerFixture

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node


def extract_tool_calls_from_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract tool calls from message list."""
    tool_calls = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                    }
                )
    return tool_calls


@pytest.fixture
def mock_user_state() -> AgentState:
    """Base user state for routing tests."""
    return AgentState(
        messages=[],
        user_email="test@example.com",
        league_id="12345",
        team_id="1",
        thread_id=str(uuid.uuid4()),
        user_teams=[
            {
                "league_id": "12345",
                "team_id": "1",
                "team_name": "Test Team",
                "game_key": "nhl.l.12345",
                "league_name": "Test League",
            }
        ],
    )


@pytest.fixture
def mock_yahoo_tools(mocker: MockerFixture) -> None:
    """Mock Yahoo tools to prevent API calls during routing tests."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    # Mock get_user_teams_with_league_info on the repository
    mocker.patch(
        "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
        return_value=[
            {
                "league_id": "12345",
                "team_id": "1",
                "team_name": "Test Team",
                "game_key": "nhl.l.12345",
                "league_name": "Test League",
            }
        ],
    )

    # Mock OAuth tokens to simulate authenticated user
    mocker.patch(
        "data.yahoo_token_repository.load_tokens_from_db",
        return_value={"access_token": "test_token", "refresh_token": "test_refresh"},
    )

    # Mock memory store to simulate returning user (not first-time)
    mock_memory_store = MagicMock()
    mock_memory_store.search.return_value = [{"content": "past conversation"}]
    mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

    # Create mock player data using SimpleNamespace for proper attribute access
    mock_players = [
        SimpleNamespace(
            name=SimpleNamespace(full="Timo Meier"),
            player_key="nhl.p.6749",
            player_id="6749",
            display_position="RW",
            editorial_team_abbr="NJD",
            editorial_team_full_name="New Jersey Devils",
            status="healthy",
            status_full=None,
            player_stats=SimpleNamespace(total_points=45.0),
        ),
    ]

    # Create mock client with properly configured query methods
    mock_client = MagicMock()
    mock_client.query.get_league_key.return_value = "nhl.l.12345"
    mock_client.query.get_team_roster_player_stats.return_value = mock_players
    mock_client.query.get_league_teams.return_value = []

    # Patch AuthenticatedYahooClient in modules
    yahoo_tool_modules = [
        "tools.yahoo.get_team_roster",
        "tools.yahoo.get_league_teams",
        "tools.yahoo.find_similar_ranked_players",
        "tools.yahoo.get_player_season_rank",
        "tools.yahoo.get_roster",
        "tools.yahoo.get_player_yahoo_info",
        "tools.available.search_available_players",
        "tools.yahoo.onboard_user_team",
        "tools.yahoo.get_user_leagues",
    ]

    for module in yahoo_tool_modules:
        mocker.patch(
            f"{module}.AuthenticatedYahooClient",
            return_value=mock_client,
        )


class TestNotificationRouting:
    """Test that notification requests route to manage_notifications tool."""

    def test_stop_digest_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """'Stop sending me weekly digests' routes to manage_notifications with enabled=False."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me weekly digests")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        # Find manage_notifications call
        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        # Verify enabled=False
        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is False, (
            f"Expected enabled=False, got: {call_args}"
        )

    def test_unsubscribe_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """'Unsubscribe from the weekly emails' routes to manage_notifications with enabled=False."""
        mock_user_state["messages"] = [
            HumanMessage(content="Unsubscribe from the weekly emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        # Find manage_notifications call
        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call for unsubscribe request, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        # Verify enabled=False
        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is False, (
            f"Expected enabled=False for unsubscribe, got: {call_args}"
        )

    def test_turn_on_digest_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """'Turn the weekly digest back on' routes to manage_notifications with enabled=True."""
        mock_user_state["messages"] = [
            HumanMessage(content="Turn the weekly digest back on")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        # Find manage_notifications call
        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call for enable request, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        # Verify enabled=True
        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is True, (
            f"Expected enabled=True for re-enable request, got: {call_args}"
        )

    def test_notification_tool_receives_correct_user_email(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """manage_notifications receives the correct user_email from state."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me the weekly digest")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        if notification_calls:
            call_args = notification_calls[0]["args"]
            # The tool should receive the user's email
            assert call_args.get("user_email") == "test@example.com", (
                f"Expected user_email='test@example.com', got: {call_args}"
            )

    def test_notification_tool_receives_correct_league_id(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """manage_notifications receives the correct league_id from state."""
        mock_user_state["messages"] = [
            HumanMessage(content="Please turn off the weekly digest")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        if notification_calls:
            call_args = notification_calls[0]["args"]
            # The tool should receive the user's league_id
            assert call_args.get("league_id") == "12345", (
                f"Expected league_id='12345', got: {call_args}"
            )

    def test_notification_tool_uses_weekly_digest_type(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """manage_notifications uses 'weekly_digest' as the notification type."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop the weekly digest emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        if notification_calls:
            call_args = notification_calls[0]["args"]
            # Should use weekly_digest as notification type
            assert call_args.get("notification_type") == "weekly_digest", (
                f"Expected notification_type='weekly_digest', got: {call_args}"
            )
