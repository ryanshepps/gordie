"""Unit tests for supervisor agent routing logic.

These tests verify that the supervisor correctly routes requests to the appropriate
tools/subagents without needing LLM-as-judge evaluation.
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

    # Mock get_user_teams - must patch where it's used (context_validator), not where it's defined
    mocker.patch(
        "agent.context_validator.get_user_teams",
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
        SimpleNamespace(
            name=SimpleNamespace(full="Jack Hughes"),
            player_key="nhl.p.7910",
            player_id="7910",
            display_position="C",
            editorial_team_abbr="NJD",
            editorial_team_full_name="New Jersey Devils",
            status="healthy",
            status_full=None,
            player_stats=SimpleNamespace(total_points=85.0),
        ),
    ]

    # Create mock team data for get_league_teams
    mock_manager = SimpleNamespace(
        nickname="TestManager",
        email="manager@test.com",
        is_commissioner=False,
    )
    mock_teams = [
        SimpleNamespace(
            team_id="1",
            team_key="nhl.l.12345.t.1",
            name="Test Team",
            managers=[mock_manager],
            waiver_priority=5,
            number_of_moves=10,
            number_of_trades=2,
            team_standings=SimpleNamespace(
                rank=3,
                playoff_seed=3,
                points_for=150.0,
                points_against=120.0,
                outcome_totals=SimpleNamespace(wins=10, losses=5, ties=2),
            ),
        ),
        SimpleNamespace(
            team_id="2",
            team_key="nhl.l.12345.t.2",
            name="Opponent Team",
            managers=[
                SimpleNamespace(nickname="Opponent", email="opp@test.com", is_commissioner=False)
            ],
            waiver_priority=3,
            number_of_moves=8,
            number_of_trades=1,
            team_standings=SimpleNamespace(
                rank=1,
                playoff_seed=1,
                points_for=180.0,
                points_against=100.0,
                outcome_totals=SimpleNamespace(wins=14, losses=3, ties=0),
            ),
        ),
    ]

    # Create mock response for get_response (used by find_similar_ranked_players)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "fantasy_content": {
            "league": [
                {"league_key": "nhl.l.12345"},
                {
                    "players": {
                        "0": {
                            "player": [
                                [
                                    {"name": {"full": "Timo Meier"}},
                                    {"player_key": "nhl.p.6749"},
                                    {"player_id": "6749"},
                                    {"display_position": "RW"},
                                    {"editorial_team_abbr": "NJD"},
                                    {"editorial_team_full_name": "New Jersey Devils"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Opponent Team",
                                            "owner_team_key": "nhl.l.12345.t.2",
                                        }
                                    },
                                ]
                            ]
                        },
                        "1": {
                            "player": [
                                [
                                    {"name": {"full": "Kyle Palmieri"}},
                                    {"player_key": "nhl.p.5020"},
                                    {"player_id": "5020"},
                                    {"display_position": "RW"},
                                    {"editorial_team_abbr": "NYI"},
                                    {"editorial_team_full_name": "New York Islanders"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Another Team",
                                            "owner_team_key": "nhl.l.12345.t.3",
                                        }
                                    },
                                ]
                            ]
                        },
                        "count": 2,
                    }
                },
            ]
        }
    }

    # Create mock client with properly configured query methods
    mock_client = MagicMock()
    mock_client.query.get_league_key.return_value = "nhl.l.12345"
    mock_client.query.get_team_roster_player_stats.return_value = mock_players
    mock_client.query.get_league_teams.return_value = mock_teams
    mock_client.query.get_response.return_value = mock_response

    # Patch AuthenticatedYahooClient in modules
    yahoo_tool_modules = [
        "tools.yahoo.get_team_roster",
        "tools.yahoo.get_league_teams",
        "tools.yahoo.find_similar_ranked_players",
        "tools.yahoo.get_player_season_rank",
        "tools.yahoo.get_roster",
        "tools.yahoo.get_available_players",
        "tools.yahoo.onboard_user_team",
        "tools.yahoo.get_user_leagues",
    ]

    for module in yahoo_tool_modules:
        mocker.patch(
            f"{module}.AuthenticatedYahooClient",
            return_value=mock_client,
        )


class TestPlayerDropRouting:
    """Test that player drop requests route to appropriate tools."""

    def test_uses_subagents_for_drop_decision(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """Verify agent delegates to subagents for drop decisions."""
        mock_user_state["messages"] = [HumanMessage(content="Should I drop Timo Meier?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        uses_subagents = any(
            tool in tool_names
            for tool in ["trade", "available_players"]
        )

        assert uses_subagents, f"Expected 'trade' or 'available_players' subagent, got: {tool_names}"


class TestTradeRouting:
    """Test that trade requests route to the trade subagent."""

    def test_delegates_to_trade_subagent(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """Verify the agent delegates trade requests to the trade sub-agent."""
        mock_user_state["messages"] = [
            HumanMessage(content="I want to trade away Draisaitl, who should I target?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "trade" in tool_names, f"Expected 'trade' in tool calls, got: {tool_names}"

    def test_uses_find_undervalued_players_tool(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: None,
    ) -> None:
        """Verify the agent uses find_undervalued_players for trade acquisition requests."""
        mock_user_state["messages"] = [
            HumanMessage(content="Find me some undervalued players I could trade for")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        # Should use either find_undervalued_players directly or the trade sub-agent
        uses_undervalued_tool = "find_undervalued_players" in tool_names
        uses_trade_agent = "trade" in tool_names

        assert uses_undervalued_tool or uses_trade_agent, (
            f"Expected 'find_undervalued_players' or 'trade' in tool calls, got: {tool_names}"
        )
