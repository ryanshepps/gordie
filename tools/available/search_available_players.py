"""Tool to search for available players (free agents and waivers) in a fantasy league."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


def _extract_player_info(player_data: list[object]) -> dict[str, str | None]:
    """Extract player info from the raw Yahoo API player data structure."""
    player_info: dict[str, str | None] = {
        "name": "Unknown",
        "player_key": None,
        "player_id": None,
        "position": None,
        "team": None,
        "status": "available",
        "injury_status": None,
        "percent_owned": None,
        "availability_type": None,
    }

    if not player_data or not isinstance(player_data, list):
        return player_info

    attrs_list = player_data[0] if player_data else []
    if not isinstance(attrs_list, list):
        return player_info

    for attr_dict in attrs_list:
        if not isinstance(attr_dict, dict):
            continue

        if "name" in attr_dict:
            name_data = attr_dict["name"]
            if isinstance(name_data, dict):
                player_info["name"] = name_data.get("full", "Unknown")
            else:
                player_info["name"] = str(name_data)
        elif "player_key" in attr_dict:
            player_info["player_key"] = attr_dict["player_key"]
        elif "player_id" in attr_dict:
            player_info["player_id"] = attr_dict["player_id"]
        elif "display_position" in attr_dict:
            player_info["position"] = attr_dict["display_position"]
        elif "editorial_team_abbr" in attr_dict:
            player_info["team"] = attr_dict["editorial_team_abbr"]
        elif "status" in attr_dict:
            player_info["status"] = attr_dict["status"]
        elif "status_full" in attr_dict:
            player_info["injury_status"] = attr_dict["status_full"]
        elif "percent_owned" in attr_dict:
            pct_data = attr_dict["percent_owned"]
            if isinstance(pct_data, dict):
                player_info["percent_owned"] = pct_data.get("value")
            else:
                player_info["percent_owned"] = str(pct_data) if pct_data else None

    return player_info


@tool
def search_available_players(
    user_email: str,
    league_id: str,
    status: str = "A",
    position: str = "",
    sort: str = "AR",
    sort_type: str = "season",
    count: int = 25,
) -> str:
    """
    Search for available players (free agents and/or waivers) in a fantasy league.

    Returns basic player info: name, team, position, ownership %, availability type.
    Use query_stats_db to fetch detailed statistics for specific players.

    Args:
        user_email: User's email for Yahoo authentication
        league_id: Yahoo league ID
        status: Availability filter
            - "A" = All available (free agents + waivers)
            - "FA" = Free agents only (can add immediately)
            - "W" = Waivers only (require waiver claim)
        position: Position filter (C, LW, RW, D, G, F for all forwards, or empty for all)
        sort: Sort order
            - "AR" = Actual rank (by fantasy points - best for finding top performers)
            - "OR" = Ownership rank (by % owned - best for popular players)
            - "PTS" = Fantasy points
        sort_type: Time period for sorting
            - "season" = Full season stats
            - "lastweek" = Last week's stats (good for hot streaks)
            - "lastmonth" = Last month's stats
        count: Number of players to return (max 50)

    Returns:
        JSON with list of available players including name, team, position,
        percent_owned, and availability_type (FA or W).

    Examples:
        - Top available players this season: sort="AR", sort_type="season"
        - Hot players last week: sort="AR", sort_type="lastweek"
        - Most owned available: sort="OR"
        - Available centers only: position="C"
        - Free agents only: status="FA"
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        league_key = yahoo_client.query.get_league_key()

        # Clamp count to reasonable limit
        count = min(count, 50)

        # Build filter parameters
        filters = [
            f"status={status}",
            f"count={count}",
            f"sort={sort}",
            f"sort_type={sort_type}",
        ]
        if position:
            filters.append(f"position={position}")

        filter_str = ";".join(filters)
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

        logger.info(f"Searching available players: {url}")

        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        if not isinstance(league_data, list) or len(league_data) < 2:
            logger.warning("Unexpected league data structure in response")
            return json.dumps({"players": [], "count": 0})

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        result = []

        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    player_info = _extract_player_info(player_data)

                    # Determine availability type from status filter or player status
                    if status == "FA":
                        player_info["availability_type"] = "FA"
                    elif status == "W":
                        player_info["availability_type"] = "W"
                    else:
                        # For status="A", we need to check the player's actual status
                        # The API doesn't always return this clearly, default to FA
                        player_info["availability_type"] = player_info.get("status", "FA")

                    result.append(player_info)

        return json.dumps(
            {
                "players": result,
                "count": len(result),
                "filters": {
                    "status": status,
                    "position": position or "all",
                    "sort": sort,
                    "sort_type": sort_type,
                },
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error searching available players: {e}")
        return json.dumps({"error": str(e), "players": [], "count": 0})
