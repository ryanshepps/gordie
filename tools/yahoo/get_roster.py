"""Tool to get your current fantasy hockey roster."""

import sys

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


@tool
def get_roster(user_email: str, league_id: str, team_id: str) -> str:
    """
    Get the current roster for a fantasy hockey team with player stats and positions.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        team_id: Yahoo team ID

    Returns:
        JSON string with roster information including player names, positions,
        NHL teams, fantasy points, and injury status.
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)
    yahoo_query = yahoo_client.query

    try:
        roster = yahoo_query.get_team_roster_player_stats(team_id)
        return str(roster)
    except Exception as e:
        logger.error(f"Error fetching roster: {e}")
        sys.exit(1)
