"""Evals for available players subagent - streaming and pickup/drop analysis."""

import json
import re

import pytest
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

MOCK_PLAYER_DATA = {
    "Teuvo Teravainen": {"id": 8475168, "team": "CHI", "position": "RW"},
    "Brock Boeser": {"id": 8478444, "team": "VAN", "position": "RW"},
    "Jake Guentzel": {"id": 8477404, "team": "TBL", "position": "LW"},
    "Kevin Fiala": {"id": 8477942, "team": "LAK", "position": "LW"},
    "Pavel Buchnevich": {"id": 8477402, "team": "STL", "position": "RW"},
    "Dylan Cozens": {"id": 8481528, "team": "BUF", "position": "C"},
    "Brock Nelson": {"id": 8475754, "team": "NYI", "position": "C"},
    "Timo Meier": {"id": 8478414, "team": "NJD", "position": "LW"},
}

MOCK_PLAYER_IDS = {name: data["id"] for name, data in MOCK_PLAYER_DATA.items()}


def _build_mock_fuzzy_resolve_response(player_names: list[str]) -> str:
    """Build mock response for fuzzy_resolve_nhl_api_player_ids."""
    result = {}
    for name in player_names:
        if name in MOCK_PLAYER_DATA:
            data = MOCK_PLAYER_DATA[name]
            result[name] = {
                "status": "success",
                "source": "moneypuck",
                "player_id": data["id"],
                "full_name": name,
                "team_abbrev": data["team"],
                "position": data["position"],
            }
        else:
            result[name] = {
                "status": "not_found",
                "message": f"No player found matching '{name}'",
            }
    return json.dumps(result)


MOCK_CLI_STATS = {
    "Teuvo Teravainen": {
        "name": "Teuvo Teravainen", "team": "CHI", "position": "RW",
        "games_played": 35, "goals": 12, "points": 32, "x_goals": 10.5,
        "fenwick_pct": 52.3, "corsi_pct": 51.0, "toi_per_game_minutes": 17.5,
        "points_per_game": 0.91,
    },
    "Brock Boeser": {
        "name": "Brock Boeser", "team": "VAN", "position": "RW",
        "games_played": 38, "goals": 15, "points": 33, "x_goals": 12.0,
        "fenwick_pct": 51.5, "corsi_pct": 50.8, "toi_per_game_minutes": 18.0,
        "points_per_game": 0.87,
    },
    "Jake Guentzel": {
        "name": "Jake Guentzel", "team": "TBL", "position": "LW",
        "games_played": 40, "goals": 18, "points": 40, "x_goals": 16.0,
        "fenwick_pct": 54.1, "corsi_pct": 53.5, "toi_per_game_minutes": 19.5,
        "points_per_game": 1.0,
    },
    "Kevin Fiala": {
        "name": "Kevin Fiala", "team": "LAK", "position": "LW",
        "games_played": 36, "goals": 14, "points": 36, "x_goals": 12.0,
        "fenwick_pct": 53.0, "corsi_pct": 52.5, "toi_per_game_minutes": 18.2,
        "points_per_game": 1.0,
    },
    "Pavel Buchnevich": {
        "name": "Pavel Buchnevich", "team": "STL", "position": "RW",
        "games_played": 37, "goals": 13, "points": 35, "x_goals": 11.5,
        "fenwick_pct": 51.8, "corsi_pct": 51.0, "toi_per_game_minutes": 17.8,
        "points_per_game": 0.95,
    },
    "Dylan Cozens": {
        "name": "Dylan Cozens", "team": "BUF", "position": "C",
        "games_played": 38, "goals": 11, "points": 34, "x_goals": 10.0,
        "fenwick_pct": 50.5, "corsi_pct": 50.0, "toi_per_game_minutes": 17.0,
        "points_per_game": 0.89,
    },
    "Brock Nelson": {
        "name": "Brock Nelson", "team": "NYI", "position": "C",
        "games_played": 39, "goals": 16, "points": 36, "x_goals": 14.0,
        "fenwick_pct": 52.0, "corsi_pct": 51.5, "toi_per_game_minutes": 18.5,
        "points_per_game": 0.92,
    },
    "Timo Meier": {
        "name": "Timo Meier", "team": "NJD", "position": "LW",
        "games_played": 38, "goals": 10, "points": 28, "x_goals": 14.0,
        "fenwick_pct": 48.2, "corsi_pct": 47.5, "toi_per_game_minutes": 16.5,
        "points_per_game": 0.74,
    },
}


def _mock_run_moneypuck_query(command: str) -> str:
    """Mock run_moneypuck_query returning JSON stats for player stats commands."""
    for name, stats in MOCK_CLI_STATS.items():
        if name.lower() in command.lower() or name.split()[-1].lower() in command.lower():
            return json.dumps(stats)
    return json.dumps({"error": "Player not found"})


def _build_mock_player_schedule() -> str:
    """Build mock response for get_team_schedule tool.

    Note: Dates are intentionally historical (2024-12-XX) rather than relative
    for test determinism. The agent evaluates schedule density, not absolute dates.
    """
    return json.dumps({
        "CHI": {
            "team": "Chicago Blackhawks",
            "games_this_week": 3,
            "games_next_week": 4,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "DET", "home": True},
                {"date": "2024-12-26", "opponent": "STL", "home": False},
                {"date": "2024-12-28", "opponent": "COL", "home": True},
            ],
        },
        "VAN": {
            "team": "Vancouver Canucks",
            "games_this_week": 2,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-24", "opponent": "SEA", "home": True},
                {"date": "2024-12-27", "opponent": "CGY", "home": False},
            ],
        },
        "TBL": {
            "team": "Tampa Bay Lightning",
            "games_this_week": 4,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "FLA", "home": True},
                {"date": "2024-12-25", "opponent": "CAR", "home": False},
                {"date": "2024-12-27", "opponent": "NYR", "home": True},
                {"date": "2024-12-28", "opponent": "BOS", "home": True},
            ],
        },
        "NJD": {
            "team": "New Jersey Devils",
            "games_this_week": 2,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-24", "opponent": "PHI", "home": True},
                {"date": "2024-12-27", "opponent": "NYI", "home": False},
            ],
        },
        "LAK": {
            "team": "Los Angeles Kings",
            "games_this_week": 3,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "ANA", "home": True},
                {"date": "2024-12-26", "opponent": "SJS", "home": False},
                {"date": "2024-12-28", "opponent": "VGK", "home": True},
            ],
        },
        "STL": {
            "team": "St. Louis Blues",
            "games_this_week": 3,
            "games_next_week": 4,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "MIN", "home": True},
                {"date": "2024-12-26", "opponent": "CHI", "home": True},
                {"date": "2024-12-28", "opponent": "NSH", "home": False},
            ],
        },
        "BUF": {
            "team": "Buffalo Sabres",
            "games_this_week": 2,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-24", "opponent": "OTT", "home": True},
                {"date": "2024-12-27", "opponent": "TOR", "home": False},
            ],
        },
        "NYI": {
            "team": "New York Islanders",
            "games_this_week": 3,
            "games_next_week": 3,
            "upcoming_games": [
                {"date": "2024-12-23", "opponent": "WSH", "home": True},
                {"date": "2024-12-26", "opponent": "PIT", "home": False},
                {"date": "2024-12-27", "opponent": "NJD", "home": True},
            ],
        },
    })


@pytest.fixture
def mock_stats_tools(mocker):
    """Set up all stats tool mocks for available player tests."""
    mocker.patch(
        "tools.stats.run_moneypuck_query.subprocess.run",
        side_effect=lambda args, **kwargs: type("Result", (), {
            "stdout": _mock_run_moneypuck_query(" ".join(args[3:])),
            "stderr": "",
            "returncode": 0,
        })(),
    )
    mocker.patch(
        "tools.stats.get_player_schedule.fuzzy_resolve_nhl_api_player_ids",
        side_effect=_build_mock_fuzzy_resolve_response,
    )
    mocker.patch(
        "tools.stats.get_player_schedule.get_team_schedule",
        return_value=_build_mock_player_schedule(),
    )


def _get_response_text(result) -> str:
    """Extract response text from supervisor result."""
    update = result.update or {}
    return update.get("response", "")  # type: ignore[union-attr]


def _response_mentions_any_player(response: str) -> bool:
    """Check if response mentions any known player name."""
    response_lower = response.lower()
    return any(name.lower() in response_lower for name in MOCK_PLAYER_DATA)


def _response_mentions_stats(response: str) -> bool:
    """Check if response mentions statistical terms."""
    stats_patterns = [
        r"\bgoals?\b",
        r"\bpoints?\b",
        r"\bassists?\b",
        r"\bxgoals?\b",
        r"\bfenwick\b",
        r"\bcorsi\b",
        r"\bgames?\s*played\b",
    ]
    response_lower = response.lower()
    return any(re.search(pattern, response_lower) for pattern in stats_patterns)


def _response_mentions_schedule(response: str) -> bool:
    """Check if response mentions schedule-related terms."""
    schedule_patterns = [
        r"\bgames?\s*(this|next)?\s*week\b",
        r"\bschedule\b",
        r"\bupcoming\b",
        r"\b[2-4]\s*games?\b",
        r"\bstreaming\b",
    ]
    response_lower = response.lower()
    return any(re.search(pattern, response_lower) for pattern in schedule_patterns)


@pytest.mark.integration
@pytest.mark.parametrize(
    "user_input,required_checks",
    [
        pytest.param(
            "Who are the best available players I should pick up for streaming this week?",
            ["players", "stats"],
            id="general_recommendations",
        ),
        pytest.param(
            "I need streaming options for this week - who has the best schedule?",
            ["players", "schedule"],
            id="schedule_streaming",
        ),
        pytest.param(
            "Who are the best available players based on advanced stats?",
            ["players", "stats"],
            id="advanced_stats",
        ),
    ],
)
@retry_on_rate_limit(max_retries=3, base_delay=2.0)
def test_available_player_recommendations(
    mock_user_state, mock_yahoo_tools, mock_stats_tools, user_input, required_checks
):
    """Verify response includes player recommendations with relevant context.

    Tests that the agent:
    - Mentions specific players when asked about available players
    - Includes stats when stats are relevant to the query
    - Includes schedule info when schedule is relevant to the query
    """
    mock_user_state["messages"] = [HumanMessage(content=user_input)]

    result = supervisor_node(mock_user_state)
    response_text = _get_response_text(result)

    errors = []
    if "players" in required_checks and not _response_mentions_any_player(response_text):
        errors.append("Response should mention at least one player name")
    if "stats" in required_checks and not _response_mentions_stats(response_text):
        errors.append("Response should mention statistical information")
    if "schedule" in required_checks and not _response_mentions_schedule(response_text):
        errors.append("Response should mention schedule information")

    assert not errors, f"Response validation failed: {errors}\n\nResponse: {response_text}"


@pytest.mark.integration
@retry_on_rate_limit(max_retries=3, base_delay=2.0)
def test_player_comparison(mock_user_state, mock_yahoo_tools, mock_stats_tools):
    """Verify agent can compare two specific players.

    This tests a distinct feature: when a user asks about specific players,
    the response should mention both players and provide comparative analysis.
    """
    user_input = "Should I pick up Teuvo Teravainen or Brock Boeser?"
    mock_user_state["messages"] = [HumanMessage(content=user_input)]

    result = supervisor_node(mock_user_state)
    response_text = _get_response_text(result)
    response_lower = response_text.lower()

    mentions_teravainen = "teravainen" in response_lower
    mentions_boeser = "boeser" in response_lower

    errors = []
    if not mentions_teravainen:
        errors.append("Response should mention Teravainen")
    if not mentions_boeser:
        errors.append("Response should mention Boeser")
    if not (mentions_teravainen and mentions_boeser):
        errors.append("Response should compare both players")

    assert not errors, f"Comparison validation failed: {errors}\n\nResponse: {response_text}"


@pytest.mark.integration
@retry_on_rate_limit(max_retries=3, base_delay=2.0)
def test_drop_candidate_evaluation(mock_user_state, mock_yahoo_tools, mock_stats_tools):
    """Verify agent handles user-specified drop candidate correctly.

    This tests a distinct feature: when a user asks about dropping a specific
    player, the response should acknowledge that player and address the drop decision.
    """
    user_input = "Should I drop Timo Meier to pick up someone better?"
    mock_user_state["messages"] = [HumanMessage(content=user_input)]

    result = supervisor_node(mock_user_state)
    response_text = _get_response_text(result)
    response_lower = response_text.lower()

    mentions_meier = "meier" in response_lower

    # Check for drop-related language
    drop_patterns = [r"\bdropp?(ing)?\b", r"\bkeep\b", r"\bhold\b", r"\broster\b"]
    discusses_drop = any(re.search(p, response_lower) for p in drop_patterns)

    errors = []
    if not mentions_meier:
        errors.append("Response should mention Timo Meier")
    if not discusses_drop:
        errors.append("Response should discuss the drop decision")

    assert not errors, f"Drop candidate validation failed: {errors}\n\nResponse: {response_text}"
