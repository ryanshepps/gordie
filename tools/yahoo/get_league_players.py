"""Tool to get all players in a fantasy hockey league (both rostered and available)."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


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

        # Use the query method directly
        players_data = yahoo_client.query.query(url, ["league", "players"])

        if not players_data:
            return json.dumps({"players": [], "message": "No players found matching criteria"})

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
                "ownership_type": getattr(player, "ownership_type", None),
                "owner_team_name": getattr(player, "owner_team_name", None),
                "status": getattr(player, "status", None),
                "injury_status": getattr(player, "status_full", None),
                "percent_owned": percent_owned_value,
            }
            result.append(player_info)

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
