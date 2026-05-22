"""Tool to get player line information and linemates by player name."""

import json
from typing import Any

from langchain.tools import tool

from module.logger import get_logger
from tools.hockey.player.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.hockey.player.get_player_line_info import (
    get_player_line_info as get_player_line_info_by_id,
)

logger = get_logger(__name__)


@tool
def get_player_line_info(
    player_names: list[str],
) -> str:
    """
    Get line deployment and linemate information for NHL players.

    Analyzes shift data from recent games to determine player usage.

    Args:
        player_names: List of player names (e.g., ["Connor McDavid", "Auston Matthews"])

    Returns:
        JSON with per-player line info:
        - estimated_line_number: Line/pairing number (1-4 for forwards, 1-3 for defense)
        - primary_linemates: Top 1-2 linemates by shared ice time
          - name, position, shared_ice_time_pct
        - target_ice_time_seconds: Total ice time in analyzed game

    Note:
        Line number is estimated from ice time ranking among position group.
        1st line players typically get 18-22 min/game, 4th line gets 8-12 min.
        Playing with elite linemates (McDavid, Matthews) boosts fantasy value.
    """
    # Step 1: Resolve player names to NHL IDs
    logger.info(f"Resolving {len(player_names)} player names for line info")
    resolved_json = fuzzy_resolve_nhl_api_player_ids(player_names)
    resolved: dict[str, dict[str, Any]] = json.loads(resolved_json)

    # Build mapping of name -> NHL ID
    name_to_id: dict[str, int] = {}
    resolution_errors: dict[str, str] = {}

    for name, player_result in resolved.items():
        if player_result.get("status") == "success":
            name_to_id[name] = int(player_result["player_id"])
        elif player_result.get("status") == "multiple_matches":
            matches = player_result.get("matches", [])
            if matches:
                name_to_id[name] = int(matches[0]["player_id"])
            else:
                resolution_errors[name] = "Multiple matches but no results"
        else:
            resolution_errors[name] = str(player_result.get("message", "Player not found"))

    if not name_to_id:
        return json.dumps(
            {
                "error": "Could not resolve any player names",
                "resolution_errors": resolution_errors,
            }
        )

    # Step 2: Fetch line info for resolved IDs
    player_ids = list(name_to_id.values())
    logger.info(f"Fetching line info for {len(player_ids)} players")
    line_info_json = get_player_line_info_by_id(player_ids)
    line_info: dict[str, dict[str, Any]] = json.loads(line_info_json)

    # Step 3: Build response keyed by original player name
    result: dict[str, dict[str, Any]] = {}

    # Create ID -> name reverse mapping
    id_to_name = {v: k for k, v in name_to_id.items()}

    for player_id_str, player_info in line_info.items():
        player_id = int(player_id_str)
        original_name = id_to_name.get(player_id, player_id_str)
        result[original_name] = player_info

    # Add resolution errors
    for name, error in resolution_errors.items():
        result[name] = {"status": "error", "message": error}

    return json.dumps(result, indent=2)
