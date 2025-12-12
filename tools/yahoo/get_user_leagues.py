"""Tool to get all Yahoo Fantasy leagues for a user."""

import sys
from langchain.tools import tool
from client.AuthenticatedYahooClient import AuthenticatedYahooClient
from module.logger import get_logger


logger = get_logger(__name__)


@tool
def get_user_leagues(user_email: str) -> str:
    """
    Get all Yahoo Fantasy leagues for a user across all sports and seasons.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)

    Returns:
        String with league information including league IDs, names, and teams.
    """
    yahoo_client = AuthenticatedYahooClient(user_email=user_email)
    yahoo_query = yahoo_client.query

    try:
        user_games = yahoo_query.get_user_teams()

        # Format the output in a structured way for the AI agent
        # get_user_teams returns a list of Game objects, each containing teams
        result = []
        for game in user_games:
            for team in game.teams:
                # Extract game_key, league_id, and team_id from team_key (format: "game_key.l.league_id.t.team_id")
                if not hasattr(team, 'team_key') or not team.team_key:
                    raise ValueError("Team is missing team_key attribute")
                
                parts = team.team_key.split('.')
                if len(parts) < 5 or parts[1] != 'l' or parts[3] != 't':
                    raise ValueError(f"team_key '{team.team_key}' is not in expected format 'game_key.l.league_id.t.team_id'")
                
                game_key = parts[0]
                league_id = parts[2]
                team_id_from_key = parts[4]

                team_info = {
                    "sport": game.code if hasattr(game, 'code') else 'Unknown',
                    "season": game.season if hasattr(game, 'season') else 'Unknown',
                    "game_key": game_key,
                    "league_id": league_id,
                    "team_id": team_id_from_key,
                    "team_name": team.name if hasattr(team, 'name') else 'Unknown',
                    "is_active": not (game.is_offseason if hasattr(game, 'is_offseason') else True),
                }
                result.append(team_info)

        return str(result)
    except Exception as e:
        logger.error(f"Error fetching user leagues: {e}")
        sys.exit(1)
