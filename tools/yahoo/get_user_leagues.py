"""Tool to get all Yahoo Fantasy leagues for a user."""

from langchain.tools import tool
from yfpy.exceptions import YahooFantasySportsDataNotFound

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


def _normalize_games(user_games):
    """
    Normalize user_games to always return a list of Game objects.

    yfpy's get_user_teams() returns either:
    - A list of Game objects when user has multiple games
    - A dict {'game': Game(...)} when user has a single game
    - An empty list when user has no games
    """
    if isinstance(user_games, dict):
        # Single game returned as dict
        game = user_games.get("game")
        if game:
            return [game]
        return []
    elif isinstance(user_games, list):
        return user_games
    else:
        logger.warning(f"Unexpected user_games type: {type(user_games)}")
        return []


def _normalize_teams(teams_data):
    """
    Normalize teams_data to always return a list of Team objects.

    Game.teams can be either:
    - A list of Team objects when game has multiple teams
    - A dict {'team': Team(...)} when game has a single team
    - A string error message when Yahoo returns an error
    """
    if isinstance(teams_data, str):
        # Error message from Yahoo
        logger.error(f"Yahoo returned error for teams: {teams_data}")
        return []
    elif isinstance(teams_data, dict):
        # Single team returned as dict
        team = teams_data.get("team")
        if team:
            return [team]
        return []
    elif isinstance(teams_data, list):
        return teams_data
    else:
        logger.warning(f"Unexpected teams_data type: {type(teams_data)}")
        return []


@tool
def get_user_leagues(user_id: str) -> str:
    """
    Get all Yahoo Fantasy leagues for a user across all sports and seasons.

    Args:
        user_id: Canonical user UUID used to look up OAuth tokens

    Returns:
        String with league information including league IDs, names, and teams.
    """
    yahoo_client = AuthenticatedYahooClient(user_id=user_id)
    yahoo_query = yahoo_client.query

    try:
        user_games = yahoo_query.get_user_teams()

        # Normalize to list of Game objects
        games = _normalize_games(user_games)
        logger.info(f"Found {len(games)} game(s) for user_id={user_id}")

        result = []
        for game in games:
            if not hasattr(game, "teams"):
                logger.error(f"Game object missing teams attribute: {type(game)}")
                continue

            # Normalize teams to list
            teams = _normalize_teams(game.teams)

            for team in teams:
                if not hasattr(team, "team_key") or not team.team_key:
                    logger.warning(f"Team missing team_key: {team}")
                    continue

                parts = team.team_key.split(".")
                if len(parts) < 5 or parts[1] != "l" or parts[3] != "t":
                    logger.warning(f"Invalid team_key format: {team.team_key}")
                    continue

                game_key = parts[0]
                league_id = parts[2]
                team_id_from_key = parts[4]

                team_name = team.name if hasattr(team, "name") else "Unknown"
                if isinstance(team_name, bytes):
                    team_name = team_name.decode("utf-8")

                team_info = {
                    "sport": game.code if hasattr(game, "code") else "Unknown",
                    "season": game.season if hasattr(game, "season") else "Unknown",
                    "game_key": game_key,
                    "league_id": league_id,
                    "team_id": team_id_from_key,
                    "team_name": team_name,
                    "is_active": not (game.is_offseason if hasattr(game, "is_offseason") else True),
                }
                result.append(team_info)

        return str(result)
    except YahooFantasySportsDataNotFound:
        logger.info(f"User {user_id} has no Yahoo Fantasy leagues")
        return "[]"
    except Exception as e:
        logger.error(f"Error fetching user leagues: {e}", exc_info=True)
        return "Error fetching user leagues"
