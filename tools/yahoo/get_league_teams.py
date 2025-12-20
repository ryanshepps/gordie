"""Tool to get all teams in a fantasy hockey league with their managers."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


@tool
def get_league_teams(
    user_email: str,
    league_id: str,
) -> str:
    """
    Get all teams in a fantasy hockey league with their managers.

    Use this to find out who manages each team in the league, which is essential
    for proposing trades to specific managers.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID

    Returns:
        JSON string with all teams in the league including team names, manager names,
        team IDs, and standings information.
    """
    yahoo_client = AuthenticatedYahooClient(
        league_id=int(league_id), user_email=user_email
    )

    try:
        teams = yahoo_client.query.get_league_teams()

        if not teams:
            return json.dumps({"teams": [], "message": "No teams found in league"})

        # Convert to list if single result
        teams_list = teams if isinstance(teams, list) else [teams]

        result = []
        for team in teams_list:
            # Extract manager info
            managers = getattr(team, "managers", [])
            manager_info = []
            if managers:
                managers_list = managers if isinstance(managers, list) else [managers]
                for manager in managers_list:
                    manager_info.append({
                        "nickname": getattr(manager, "nickname", None),
                        "email": getattr(manager, "email", None),
                        "is_commissioner": getattr(manager, "is_commissioner", False),
                    })

            # Handle team name which may be returned as bytes
            team_name = getattr(team, "name", None)
            if isinstance(team_name, bytes):
                team_name = team_name.decode("utf-8")

            team_info = {
                "team_id": getattr(team, "team_id", None),
                "team_key": getattr(team, "team_key", None),
                "name": team_name,
                "managers": manager_info,
                "waiver_priority": getattr(team, "waiver_priority", None),
                "number_of_moves": getattr(team, "number_of_moves", None),
                "number_of_trades": getattr(team, "number_of_trades", None),
            }

            # Try to get standings info if available
            team_standings = getattr(team, "team_standings", None)
            if team_standings:
                team_info["rank"] = getattr(team_standings, "rank", None)
                team_info["playoff_seed"] = getattr(team_standings, "playoff_seed", None)
                team_info["points_for"] = getattr(team_standings, "points_for", None)
                team_info["points_against"] = getattr(team_standings, "points_against", None)

                outcome_totals = getattr(team_standings, "outcome_totals", None)
                if outcome_totals:
                    team_info["wins"] = getattr(outcome_totals, "wins", None)
                    team_info["losses"] = getattr(outcome_totals, "losses", None)
                    team_info["ties"] = getattr(outcome_totals, "ties", None)

            result.append(team_info)

        return json.dumps({
            "teams": result,
            "count": len(result),
            "league_id": league_id,
        })

    except Exception as e:
        logger.error(f"Error fetching league teams: {e}")
        return json.dumps({"error": str(e), "teams": []})
