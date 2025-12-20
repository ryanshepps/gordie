"""Tool to get all players in a fantasy hockey league (both rostered and available)."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


def _extract_player_info(player_data: list[object]) -> dict[str, str | None]:
    """Extract player info from the raw Yahoo API player data structure.

    The Yahoo API returns player data as a list of dicts, where each dict
    contains a single attribute. This function flattens that structure.
    """
    player_info = {
        "name": "Unknown",
        "player_key": None,
        "player_id": None,
        "position": None,
        "team": None,
        "team_full": None,
        "ownership_type": None,
        "owner_team_name": None,
        "status": None,
        "injury_status": None,
        "percent_owned": None,
    }

    if not player_data or not isinstance(player_data, list):
        return player_info

    # First element is a list of dicts with player attributes
    attrs_list = player_data[0] if player_data else []
    if not isinstance(attrs_list, list):
        return player_info

    for attr_dict in attrs_list:
        if not isinstance(attr_dict, dict):
            continue

        if "name" in attr_dict:
            name_data = attr_dict["name"]
            player_info["name"] = name_data.get("full", "Unknown") if isinstance(name_data, dict) else str(name_data)
        elif "player_key" in attr_dict:
            player_info["player_key"] = attr_dict["player_key"]
        elif "player_id" in attr_dict:
            player_info["player_id"] = attr_dict["player_id"]
        elif "display_position" in attr_dict:
            player_info["position"] = attr_dict["display_position"]
        elif "editorial_team_abbr" in attr_dict:
            player_info["team"] = attr_dict["editorial_team_abbr"]
        elif "editorial_team_full_name" in attr_dict:
            player_info["team_full"] = attr_dict["editorial_team_full_name"]
        elif "ownership" in attr_dict:
            ownership = attr_dict["ownership"]
            if isinstance(ownership, dict):
                player_info["ownership_type"] = ownership.get("ownership_type")
                player_info["owner_team_name"] = ownership.get("owner_team_name")
        elif "status" in attr_dict:
            player_info["status"] = attr_dict["status"]
        elif "status_full" in attr_dict:
            player_info["injury_status"] = attr_dict["status_full"]
        elif "percent_owned" in attr_dict:
            pct_data = attr_dict["percent_owned"]
            if isinstance(pct_data, dict):
                player_info["percent_owned"] = pct_data.get("value")
            else:
                player_info["percent_owned"] = pct_data

    return player_info


@tool
def get_league_players(
    user_email: str,
    league_id: str,
    status: str = "",
    position: str = "",
    search: str = "",
    count: int = 25,
    sort: str = "OR",
) -> str:
    """
    Get players in a fantasy hockey league with optional filters.

    Use this to search for specific players or browse players by position/status.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        status: Optional player status filter:
            - "" = All players
            - "A" = All available players (free agents + waivers)
            - "FA" = Free agents only
            - "W" = Players on waivers only
            - "T" = Taken/rostered players only
        position: Optional position filter (e.g., "C", "LW", "RW", "D", "G")
        search: Optional player name search term
        count: Maximum number of players to retrieve (default 25)
        sort: Sort order - "OR" (ownership rank), "AR" (actual rank), "PTS" (points)

    Returns:
        JSON string with player information including names, positions,
        teams, ownership status, and fantasy relevance.
    """
    yahoo_client = AuthenticatedYahooClient(
        league_id=int(league_id), user_email=user_email
    )

    try:
        league_key = yahoo_client.query.get_league_key()

        # Build filter parameters
        filters = [f"count={count}", f"sort={sort}"]
        if status:
            filters.append(f"status={status}")
        if position:
            filters.append(f"position={position}")
        if search:
            filters.append(f"search={search}")

        filter_str = ";".join(filters)
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

        logger.info(f"Fetching league players with URL: {url}")

        # Get raw response and parse manually since yfpy's query() doesn't handle
        # this endpoint's response structure correctly
        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        # league_data is a list: [league_info_dict, {players: {...}}]
        if not isinstance(league_data, list) or len(league_data) < 2:
            logger.warning("Unexpected league data structure in response")
            return json.dumps({"players": [], "message": "No players found matching criteria"})

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        # players_dict has numeric string keys ("0", "1", ...) and a "count" key
        # Each value is {"player": [[{attr1}, {attr2}, ...], ...]}
        result = []

        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    player_info = _extract_player_info(player_data)
                    result.append(player_info)
        elif isinstance(players_dict, list):
            # Handle case where it might be returned as a list
            for entry in players_dict:
                if isinstance(entry, dict) and "player" in entry:
                    player_data = entry["player"]
                    player_info = _extract_player_info(player_data)
                    result.append(player_info)

        if not result:
            return json.dumps({"players": [], "message": "No players found matching criteria"})

        return json.dumps({
            "players": result,
            "count": len(result),
            "filters": {
                "status": status or "all",
                "position": position or "all",
                "search": search or None,
            }
        })

    except Exception as e:
        logger.error(f"Error fetching league players: {e}")
        return json.dumps({"error": str(e), "players": []})
