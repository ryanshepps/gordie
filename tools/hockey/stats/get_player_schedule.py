"""Tool to get upcoming game schedule for NHL players."""

import json
from typing import Any

from langchain.tools import tool

from module.logger import get_logger
from tools.hockey.player.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.hockey.player.get_team_schedule import get_team_schedule

logger = get_logger(__name__)


@tool
def get_player_schedule(
    player_names: list[str],
) -> str:
    """
    Get upcoming game schedule for NHL players.

    This tool resolves player names to their teams and fetches schedule data.
    Useful for streaming decisions - players with more games have more scoring opportunities.

    Args:
        player_names: List of player names (e.g., ["Connor McDavid", "Auston Matthews"])

    Returns:
        JSON with per-player schedule info:
        - team: Player's NHL team abbreviation
        - games_this_week: Number of games remaining this fantasy week
        - games_next_week: Number of games next fantasy week
        - total_games: Total games in the two-week period
        - games: List of upcoming games with dates and opponents

    Note:
        Fantasy weeks typically run Monday-Sunday. More games = more opportunities
        for fantasy points. A player with 4 games vs 2 games has double the upside.
    """
    # Step 1: Resolve player names to get team info
    logger.info(f"Resolving {len(player_names)} player names")
    resolved_json = fuzzy_resolve_nhl_api_player_ids(player_names)
    resolved: dict[str, dict[str, Any]] = json.loads(resolved_json)

    # Build mapping of name -> team
    name_to_team: dict[str, str] = {}
    resolution_errors: dict[str, str] = {}

    for name, player_result in resolved.items():
        if player_result.get("status") == "success":
            team = player_result.get("team_abbrev")
            if team:
                name_to_team[name] = str(team)
            else:
                resolution_errors[name] = "Player found but no team info"
        elif player_result.get("status") == "multiple_matches":
            matches = player_result.get("matches", [])
            if matches and matches[0].get("team_abbrev"):
                name_to_team[name] = str(matches[0]["team_abbrev"])
            else:
                resolution_errors[name] = "Multiple matches but no team info"
        else:
            resolution_errors[name] = str(player_result.get("message", "Player not found"))

    if not name_to_team:
        return json.dumps(
            {
                "error": "Could not resolve any player names to teams",
                "resolution_errors": resolution_errors,
            }
        )

    # Step 2: Get unique teams and fetch schedules
    unique_teams = list(set(name_to_team.values()))
    logger.info(f"Fetching schedules for {len(unique_teams)} teams: {unique_teams}")
    schedules_json = get_team_schedule(unique_teams)
    schedules: dict[str, dict[str, Any]] = json.loads(schedules_json)

    # Step 3: Build response keyed by player name
    result: dict[str, dict[str, Any]] = {}

    for name, team in name_to_team.items():
        team_schedule = schedules.get(team, {})

        if team_schedule.get("status") == "success":
            result[name] = {
                "status": "success",
                "team": team,
                "team_name": team_schedule.get("team_name"),
                "games_this_week": team_schedule.get("this_week_games", 0),
                "games_next_week": team_schedule.get("next_week_games", 0),
                "total_games": team_schedule.get("total_games", 0),
                "period": team_schedule.get("period"),
                "games": team_schedule.get("games", []),
            }
        else:
            result[name] = {
                "status": "error",
                "team": team,
                "message": team_schedule.get("message", "Could not fetch schedule"),
            }

    # Add resolution errors
    for name, error in resolution_errors.items():
        result[name] = {"status": "error", "message": error}

    return json.dumps(result, indent=2)
