"""Shared fixtures and helpers for fantasy hockey agent evals."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from pytest_mock import MockerFixture

from agent.agent_state import AgentState


def _create_yahoo_response_handler(
    similar_ranked_players_response: dict[str, Any],
) -> Any:
    """Create a handler that returns appropriate responses based on URL."""
    from unittest.mock import MagicMock

    # Response for player search (get_player_season_rank)
    draisaitl_search_response = {
        "fantasy_content": {
            "league": [
                {"league_key": "nhl.l.12345"},
                {
                    "players": {
                        "0": {
                            "player": [
                                [
                                    {"name": {"full": "Leon Draisaitl"}},
                                    {"player_key": "nhl.p.5017"},
                                    {"player_id": "5017"},
                                    {"display_position": "C"},
                                    {"editorial_team_abbr": "EDM"},
                                    {"editorial_team_full_name": "Edmonton Oilers"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Test Team",
                                            "owner_team_key": "nhl.l.12345.t.1",
                                        }
                                    },
                                ]
                            ]
                        },
                        "count": 1,
                    }
                },
            ]
        }
    }

    def get_response_side_effect(url: str) -> MagicMock:
        response = MagicMock()
        if "search=" in url.lower():
            # Player search query (get_player_season_rank)
            response.json.return_value = draisaitl_search_response
        elif "sort=AR" in url:
            # Ranked players query (find_similar_ranked_players or rank lookup)
            response.json.return_value = similar_ranked_players_response
        else:
            # Default fallback
            response.json.return_value = similar_ranked_players_response
        return response

    return get_response_side_effect


@pytest.fixture
def mock_yahoo_tools(
    mocker: MockerFixture,
    mock_roster_response: dict[str, Any],
    mock_league_teams_response: dict[str, Any],
    mock_similar_ranked_players_response: dict[str, Any],
) -> Generator[dict[str, Any]]:
    """Mock Yahoo tools to return test data instead of calling Yahoo API."""
    # Mock get_user_teams to return test teams (prevents onboarding redirect)
    mock_get_user_teams = mocker.patch(
        "agent.SupervisorAgent.get_user_teams",
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

    # Create mock client with all necessary responses configured
    mock_client = mocker.MagicMock()
    mock_client.query.get_team_roster_player_stats.return_value = mock_roster_response
    mock_client.query.get_league_teams.return_value = mock_league_teams_response
    mock_client.query.get_league_key.return_value = "nhl.l.12345"

    # Use side_effect to return different responses based on URL
    mock_client.query.get_response.side_effect = _create_yahoo_response_handler(
        mock_similar_ranked_players_response
    )

    # Patch AuthenticatedYahooClient in ALL modules where it's imported
    # This is necessary because Python binds imports at import time
    # Note: Only include modules that actually import AuthenticatedYahooClient directly
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

    yield {"get_user_teams": mock_get_user_teams, "yahoo_client": mock_client}


@pytest.fixture
def mock_user_state() -> AgentState:
    """Base user state for evals."""
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
def mock_roster_response() -> list[Any]:
    """Mock roster including Draisaitl - returns list of player-like objects."""
    from unittest.mock import MagicMock

    players = []
    player_data = [
        {
            "name": "Leon Draisaitl",
            "player_key": "nhl.p.5017",
            "player_id": "5017",
            "position": "C",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "points": 45,
        },
        {
            "name": "Connor McDavid",
            "player_key": "nhl.p.6743",
            "player_id": "6743",
            "position": "C",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "points": 52,
        },
        {
            "name": "Timo Meier",
            "player_key": "nhl.p.6749",
            "player_id": "6749",
            "position": "LW",
            "team": "NJD",
            "team_full": "New Jersey Devils",
            "points": 28,
        },
    ]

    for data in player_data:
        player = MagicMock()
        name_obj = MagicMock()
        name_obj.full = data["name"]
        player.name = name_obj
        player.player_key = data["player_key"]
        player.player_id = data["player_id"]
        player.display_position = data["position"]
        player.editorial_team_abbr = data["team"]
        player.editorial_team_full_name = data["team_full"]
        player.status = None
        player.status_full = None

        player_stats = MagicMock()
        player_stats.total_points = data["points"]
        player.player_stats = player_stats

        players.append(player)

    return players


@pytest.fixture
def mock_moneypuck_stats() -> dict[str, Any]:
    """Mock MoneyPuck advanced stats."""
    return {
        "8477934": {  # Draisaitl
            "player_id": 8477934,
            "name": "Leon Draisaitl",
            "xGoals": 18.5,
            "goals": 20,
            "xAssists": 25.2,
            "assists": 25,
            "corsiFor": 55.2,
            "fenwickFor": 54.8,
            "icetime": 1250,
        },
        "8478402": {  # McDavid
            "player_id": 8478402,
            "name": "Connor McDavid",
            "xGoals": 22.1,
            "goals": 25,
            "corsiFor": 58.1,
            "fenwickFor": 57.5,
        },
    }


@pytest.fixture
def mock_schedule_response() -> dict[str, Any]:
    """Mock team schedule."""
    return {
        "EDM": {
            "team": "Edmonton Oilers",
            "games_this_week": 4,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "VAN", "home": True},
                {"date": "2024-12-26", "opponent": "CGY", "home": False},
            ],
        }
    }


@pytest.fixture
def mock_league_teams_response() -> list[Any]:
    """Mock league teams response from Yahoo API."""
    from unittest.mock import MagicMock

    teams = []
    team_data = [
        {"team_id": "1", "name": "Test Team", "manager": "Test User"},
        {"team_id": "2", "name": "Opponent Team A", "manager": "Opponent A"},
        {"team_id": "3", "name": "Opponent Team B", "manager": "Opponent B"},
        {"team_id": "4", "name": "Opponent Team C", "manager": "Opponent C"},
    ]

    for data in team_data:
        team = MagicMock()
        team.team_id = data["team_id"]
        team.team_key = f"nhl.l.12345.t.{data['team_id']}"
        team.name = data["name"]

        manager = MagicMock()
        manager.nickname = data["manager"]
        manager.email = f"{data['manager'].lower().replace(' ', '')}@example.com"
        manager.is_commissioner = data["team_id"] == "1"
        team.managers = [manager]

        team.waiver_priority = int(data["team_id"])
        team.number_of_moves = 5
        team.number_of_trades = 1
        team.team_standings = None

        teams.append(team)

    return teams


@pytest.fixture
def mock_similar_ranked_players_response() -> dict[str, Any]:
    """Mock response for find_similar_ranked_players Yahoo API call.

    Returns mid-tier players (rank 60-100) that are realistic trade targets,
    NOT elite superstars like McDavid/MacKinnon who would never be traded 1-for-1.
    """
    return {
        "fantasy_content": {
            "league": [
                {"league_key": "nhl.l.12345"},
                {
                    "players": {
                        "0": {
                            "player": [
                                [
                                    {"name": {"full": "Kevin Fiala"}},
                                    {"player_key": "nhl.p.7594"},
                                    {"player_id": "7594"},
                                    {"display_position": "LW"},
                                    {"editorial_team_abbr": "LAK"},
                                    {"editorial_team_full_name": "Los Angeles Kings"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Opponent Team A",
                                            "owner_team_key": "nhl.l.12345.t.2",
                                        }
                                    },
                                ]
                            ]
                        },
                        "1": {
                            "player": [
                                [
                                    {"name": {"full": "Pavel Buchnevich"}},
                                    {"player_key": "nhl.p.6921"},
                                    {"player_id": "6921"},
                                    {"display_position": "RW"},
                                    {"editorial_team_abbr": "STL"},
                                    {"editorial_team_full_name": "St. Louis Blues"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Opponent Team B",
                                            "owner_team_key": "nhl.l.12345.t.3",
                                        }
                                    },
                                ]
                            ]
                        },
                        "2": {
                            "player": [
                                [
                                    {"name": {"full": "Dylan Cozens"}},
                                    {"player_key": "nhl.p.8481528"},
                                    {"player_id": "8481528"},
                                    {"display_position": "C"},
                                    {"editorial_team_abbr": "BUF"},
                                    {"editorial_team_full_name": "Buffalo Sabres"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Opponent Team C",
                                            "owner_team_key": "nhl.l.12345.t.4",
                                        }
                                    },
                                ]
                            ]
                        },
                        "3": {
                            "player": [
                                [
                                    {"name": {"full": "Brock Nelson"}},
                                    {"player_key": "nhl.p.5699"},
                                    {"player_id": "5699"},
                                    {"display_position": "C"},
                                    {"editorial_team_abbr": "NYI"},
                                    {"editorial_team_full_name": "New York Islanders"},
                                    {
                                        "ownership": {
                                            "ownership_type": "team",
                                            "owner_team_name": "Opponent Team A",
                                            "owner_team_key": "nhl.l.12345.t.2",
                                        }
                                    },
                                ]
                            ]
                        },
                        "count": 4,
                    }
                },
            ]
        }
    }


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
