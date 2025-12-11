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
        user_teams = yahoo_query.get_user_teams()
        return str(user_teams)
    except Exception as e:
        logger.error(f"Error fetching user leagues: {e}")
        sys.exit(1)
