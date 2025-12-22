"""Tool to filter players by their NHL team."""

import json
from typing import Literal

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)

# Common NHL team abbreviations mapping
NHL_TEAM_ABBREVIATIONS = {
    # Full names to abbreviations
    "anaheim ducks": "ANA",
    "arizona coyotes": "ARI",
    "boston bruins": "BOS",
    "buffalo sabres": "BUF",
    "calgary flames": "CGY",
    "carolina hurricanes": "CAR",
    "chicago blackhawks": "CHI",
    "colorado avalanche": "COL",
    "columbus blue jackets": "CBJ",
    "dallas stars": "DAL",
    "detroit red wings": "DET",
    "edmonton oilers": "EDM",
    "florida panthers": "FLA",
    "los angeles kings": "LA",
    "minnesota wild": "MIN",
    "montreal canadiens": "MTL",
    "nashville predators": "NSH",
    "new jersey devils": "NJ",
    "new york islanders": "NYI",
    "new york rangers": "NYR",
    "ottawa senators": "OTT",
    "philadelphia flyers": "PHI",
    "pittsburgh penguins": "PIT",
    "san jose sharks": "SJ",
    "seattle kraken": "SEA",
    "st. louis blues": "STL",
    "tampa bay lightning": "TB",
    "toronto maple leafs": "TOR",
    "utah hockey club": "UTA",
    "vancouver canucks": "VAN",
    "vegas golden knights": "VGK",
    "washington capitals": "WSH",
    "winnipeg jets": "WPG",
    # Common shorthand
    "tampa bay": "TB",
    "tampa": "TB",
    "florida": "FLA",
    "panthers": "FLA",
    "lightning": "TB",
}


def normalize_team_name(team: str) -> str:
    """Normalize a team name to its abbreviation."""
    team_lower = team.lower().strip()
    if team_lower in NHL_TEAM_ABBREVIATIONS:
        return NHL_TEAM_ABBREVIATIONS[team_lower]
    # If already an abbreviation, return uppercase
    return team.upper().strip()


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
        "nhl_team": None,
        "nhl_team_full": None,
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
            player_info["nhl_team"] = attr_dict["editorial_team_abbr"]
        elif "editorial_team_full_name" in attr_dict:
            player_info["nhl_team_full"] = attr_dict["editorial_team_full_name"]
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
def filter_players_by_nhl_team(
    user_email: str,
    league_id: str,
    nhl_teams: list[str],
    mode: Literal["include", "exclude"] = "exclude",
    status: str = "A",
    position: str = "",
    count: int = 50,
) -> str:
    """
    Filter available players by their NHL team.

    Use this to find players that are NOT from specific NHL teams (useful when
    you have too many players from one team), or to find players FROM specific
    NHL teams.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        nhl_teams: List of NHL team names or abbreviations to filter by
                   (e.g., ["TB", "FLA"] or ["Tampa Bay", "Florida"])
        mode: "exclude" to find players NOT on these teams (default),
              "include" to find players ON these teams
        status: Player availability status filter:
            - "A" = All available players (free agents + waivers)
            - "FA" = Free agents only
            - "W" = Players on waivers only
            - "T" = Taken/rostered players only
        position: Optional position filter (e.g., "C", "LW", "RW", "D", "G")
        count: Maximum number of players to retrieve before filtering (default 50)

    Returns:
        JSON string with filtered player information.
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        # Normalize team names to abbreviations
        normalized_teams = {normalize_team_name(team) for team in nhl_teams}
        logger.info(f"Filtering players by NHL teams: {normalized_teams}, mode: {mode}")

        # Build the query URL
        league_key = yahoo_client.query.get_league_key()

        # Build filter parameters - get more players to filter from
        filters = [f"status={status}", f"count={count}", "sort=OR"]
        if position:
            filters.append(f"position={position}")

        filter_str = ";".join(filters)
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

        logger.info(f"Fetching players with URL: {url}")

        # Get raw response and parse manually since yfpy's query() doesn't handle
        # this endpoint's response structure correctly
        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        # league_data is a list: [league_info_dict, {players: {...}}]
        if not isinstance(league_data, list) or len(league_data) < 2:
            logger.warning("Unexpected league data structure in response")
            return json.dumps({"players": [], "message": "No players found"})

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        # Filter players by NHL team
        result = []

        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    player_info = _extract_player_info(player_data)

                    team_abbr = (player_info.get("nhl_team") or "").upper()

                    # Apply filter based on mode
                    if mode == "exclude":
                        if team_abbr in normalized_teams:
                            continue  # Skip players on excluded teams
                    else:  # include mode
                        if team_abbr not in normalized_teams:
                            continue  # Skip players NOT on included teams

                    result.append(player_info)
        elif isinstance(players_dict, list):
            for entry in players_dict:
                if isinstance(entry, dict) and "player" in entry:
                    player_data = entry["player"]
                    player_info = _extract_player_info(player_data)

                    team_abbr = (player_info.get("nhl_team") or "").upper()

                    # Apply filter based on mode
                    if mode == "exclude":
                        if team_abbr in normalized_teams:
                            continue
                    else:
                        if team_abbr not in normalized_teams:
                            continue

                    result.append(player_info)

        return json.dumps(
            {
                "players": result,
                "count": len(result),
                "filter": {
                    "nhl_teams": list(normalized_teams),
                    "mode": mode,
                    "status": status,
                    "position": position or "all",
                },
                "message": f"Found {len(result)} players {'not ' if mode == 'exclude' else ''}on {', '.join(normalized_teams)}",
            }
        )

    except Exception as e:
        logger.error(f"Error filtering players by NHL team: {e}")
        return json.dumps({"error": str(e), "players": []})
