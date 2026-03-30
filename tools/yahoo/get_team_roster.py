"""Tool to get any team's roster in a fantasy league."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


@tool
def get_team_roster(
    user_email: str,
    league_id: str,
    team_id: str,
) -> str:
    """
    Get the roster for any team in the fantasy league.

    Use this to scout other teams' rosters when looking for trade targets.
    Unlike get_roster (which only gets your own roster), this can fetch
    any team's roster by team_id.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        team_id: The team ID to fetch roster for (can be any team in the league)

    Returns:
        JSON string with roster information including player names, positions,
        NHL teams, fantasy points, and injury status.
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        roster = yahoo_client.query.get_team_roster_player_stats(team_id)

        if not roster:
            return json.dumps({"players": [], "message": "No roster found for this team"})

        # Convert to list if single result
        players = roster if isinstance(roster, list) else [roster]

        result = []
        for player in players:
            # Extract player name
            name_obj = getattr(player, "name", None)
            player_name = (
                name_obj.full
                if name_obj and hasattr(name_obj, "full")
                else str(name_obj)
                if name_obj
                else "Unknown"
            )

            # Extract player stats if available
            player_stats = getattr(player, "player_stats", None)
            total_points = None

            if player_stats:
                total_points = getattr(player_stats, "total_points", None)

            player_info = {
                "name": player_name,
                "player_key": getattr(player, "player_key", None),
                "player_id": getattr(player, "player_id", None),
                "position": getattr(player, "display_position", None),
                "team": getattr(player, "editorial_team_abbr", None),
                "team_full": getattr(player, "editorial_team_full_name", None),
                "status": getattr(player, "status", None),
                "injury_status": getattr(player, "status_full", None),
                "fantasy_points": total_points,
            }
            result.append(player_info)

        return json.dumps(
            {
                "players": result,
                "count": len(result),
                "team_id": team_id,
                "league_id": league_id,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching team roster: {e}")
        return json.dumps({"error": str(e), "players": []})
