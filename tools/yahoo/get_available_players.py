"""Tool to get available players (free agents and waivers) in a fantasy hockey league."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


@tool
def get_available_players(
    user_email: str,
    league_id: str,
    status: str = "A",
    position: str = "",
    count: int = 25,
) -> str:
    """
    Get available players (free agents and/or waivers) in a fantasy hockey league.

    Use this to find players that can be picked up or claimed from waivers.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        status: Player availability status filter:
            - "A" = All available players (free agents + waivers)
            - "FA" = Free agents only (can be added immediately)
            - "W" = Players on waivers only (require waiver claim)
        position: Optional position filter (e.g., "C", "LW", "RW", "D", "G")
        count: Maximum number of players to retrieve (default 25)

    Returns:
        JSON string with available player information including names, positions,
        teams, ownership status, and stats.
    """
    yahoo_client = AuthenticatedYahooClient(
        league_id=int(league_id), user_email=user_email
    )

    try:
        # Build the query URL with status filter
        league_key = yahoo_client.query.get_league_key()

        # Build filter parameters
        filters = [f"status={status}", f"count={count}"]
        if position:
            filters.append(f"position={position}")

        filter_str = ";".join(filters)
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

        logger.info(f"Fetching available players with URL: {url}")

        # Use the query method directly to get players with status filter
        players_data = yahoo_client.query.query(url, ["league", "players"])

        # Format the results
        if not players_data:
            return json.dumps({"players": [], "message": "No available players found"})

        # Convert to list if single result
        players = players_data if isinstance(players_data, list) else [players_data]

        # Extract relevant player info
        result = []
        for player in players:
            # Handle percent_owned which is a PercentOwned object with .value attribute
            percent_owned_obj = getattr(player, "percent_owned", None)
            percent_owned_value = None
            if percent_owned_obj is not None:
                percent_owned_value = getattr(percent_owned_obj, "value", None)

            name_obj = getattr(player, "name", None)
            player_info = {
                "name": name_obj.full if name_obj and hasattr(name_obj, "full") else "Unknown",
                "player_key": getattr(player, "player_key", None),
                "player_id": getattr(player, "player_id", None),
                "position": getattr(player, "display_position", None),
                "team": getattr(player, "editorial_team_abbr", None),
                "team_full": getattr(player, "editorial_team_full_name", None),
                "status": getattr(player, "status", "available"),
                "injury_status": getattr(player, "status_full", None),
                "percent_owned": percent_owned_value,
            }
            result.append(player_info)

        return json.dumps({"players": result, "count": len(result), "status_filter": status})

    except Exception as e:
        logger.error(f"Error fetching available players: {e}")
        return json.dumps({"error": str(e), "players": []})
