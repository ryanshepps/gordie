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
    yahoo_client = AuthenticatedYahooClient(
        league_id=int(league_id), user_email=user_email
    )

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

        players_data = yahoo_client.query.query(url, ["league", "players"])

        if not players_data:
            return json.dumps({"players": [], "message": "No players found"})

        # Convert to list if single result
        players = players_data if isinstance(players_data, list) else [players_data]

        # Filter players by NHL team
        result = []
        for player in players:
            team_abbr = getattr(player, "editorial_team_abbr", "")
            if team_abbr:
                team_abbr = team_abbr.upper()

            # Apply filter based on mode
            if mode == "exclude":
                if team_abbr in normalized_teams:
                    continue  # Skip players on excluded teams
            else:  # include mode
                if team_abbr not in normalized_teams:
                    continue  # Skip players NOT on included teams

            # Handle percent_owned
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
                "nhl_team": team_abbr,
                "nhl_team_full": getattr(player, "editorial_team_full_name", None),
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
            "filter": {
                "nhl_teams": list(normalized_teams),
                "mode": mode,
                "status": status,
                "position": position or "all",
            },
            "message": f"Found {len(result)} players {'not ' if mode == 'exclude' else ''}on {', '.join(normalized_teams)}",
        })

    except Exception as e:
        logger.error(f"Error filtering players by NHL team: {e}")
        return json.dumps({"error": str(e), "players": []})
