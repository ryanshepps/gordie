"""Tool to fetch player statistics from MoneyPuck."""

import json
from typing import Any

from langchain.tools import tool

from module.logger import get_logger
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_moneypuck_stats import get_moneypuck_stats

logger = get_logger(__name__)


@tool
def get_player_stats(
    player_names: list[str],
    situation: str = "all",
) -> str:
    """
    Get advanced statistics for NHL players from MoneyPuck.

    This tool resolves player names to NHL IDs and fetches comprehensive stats.

    Args:
        player_names: List of player names (e.g., ["Connor McDavid", "Leon Draisaitl"])
        situation: Game situation filter
            - "all" = All situations combined (default)
            - "5on5" = Even strength only
            - "5on4" = Power play only
            - "4on5" = Penalty kill only

    Returns:
        JSON with per-player statistics including:
        - Basic: games_played, goals, assists, points, points_per_game
        - Shooting: shots_on_goal, goals_per_game, shots_per_game
        - Expected: x_goals, goals_above_expected (positive = overperforming)
        - Possession: fenwick_pct, corsi_pct (higher = better, 50 is neutral)
        - Ice time: toi_minutes, toi_per_game_minutes
        - Other: hits, takeaways, giveaways, pim (penalty minutes)

    Note:
        - fenwick_pct/corsi_pct around 50% is average; >52% is good, >55% is elite
        - goals_above_expected shows shooting luck; negative values suggest regression up
        - Data is from the current NHL season
    """
    # Step 1: Resolve player names to NHL IDs
    logger.info(f"Resolving {len(player_names)} player names to NHL IDs")
    resolved_json = fuzzy_resolve_nhl_api_player_ids(player_names)
    resolved: dict[str, dict[str, Any]] = json.loads(resolved_json)

    # Build mapping of name -> NHL ID
    name_to_id: dict[str, int] = {}
    resolution_errors: dict[str, str] = {}

    for name, player_result in resolved.items():
        if player_result.get("status") == "success":
            name_to_id[name] = int(player_result["player_id"])
        elif player_result.get("status") == "multiple_matches":
            # Take the first match (most likely)
            matches = player_result.get("matches", [])
            if matches:
                name_to_id[name] = int(matches[0]["player_id"])
                logger.info(f"Multiple matches for '{name}', using first: {matches[0]['full_name']}")
            else:
                resolution_errors[name] = "Multiple matches but no results"
        else:
            resolution_errors[name] = str(player_result.get("message", "Player not found"))

    if not name_to_id:
        return json.dumps({
            "error": "Could not resolve any player names",
            "resolution_errors": resolution_errors,
        })

    # Step 2: Fetch MoneyPuck stats for resolved IDs
    player_ids = list(name_to_id.values())
    logger.info(f"Fetching MoneyPuck stats for {len(player_ids)} players")
    stats_json = get_moneypuck_stats(player_ids, situation)
    stats: dict[str, dict[str, Any]] = json.loads(stats_json)

    # Step 3: Build response keyed by original player name
    result: dict[str, dict[str, Any]] = {}

    # Create ID -> name reverse mapping
    id_to_name = {v: k for k, v in name_to_id.items()}

    for player_id_str, player_stats in stats.items():
        player_id = int(player_id_str)
        original_name = id_to_name.get(player_id, player_id_str)

        if player_stats.get("status") == "success":
            result[original_name] = {
                "status": "success",
                "situation": player_stats.get("situation"),
                "season": player_stats.get("season"),
                **player_stats.get("stats", {}),
            }
        else:
            result[original_name] = player_stats

    # Add resolution errors
    for name, error in resolution_errors.items():
        result[name] = {"status": "error", "message": error}

    return json.dumps(result, indent=2)
