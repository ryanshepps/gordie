"""Tool used to get league settings from Yahoo Fantasy API"""

import sys
from langchain.tools import tool
from client.AuthenticatedYahooClient import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)

@tool
def get_league_settings(user_email: str) -> str:
    """Get league settings from Yahoo Fantasy API

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
    """
    # Note: yahoo_email is stored in users table for informational purposes only.
    # OAuth tokens are stored and looked up using user_email in yahoo_tokens table.
    yahoo_client = AuthenticatedYahooClient(user_email=user_email)
    yahoo_query = yahoo_client.query

    try:
        league_settings = yahoo_query.get_league_settings()
        return str(league_settings)
    except Exception as e:
        logger.error(f"Error getting league settings: {e}")
        sys.exit(1)
