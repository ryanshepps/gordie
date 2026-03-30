"""Tool to get your current fantasy roster."""

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


class GetRosterInput(BaseModel):
    """Input schema for get_roster tool."""

    user_email: str = Field(
        description="User's email address (used to look up OAuth tokens in database)"
    )
    league_id: str = Field(description="Yahoo league ID (must be a valid number)")
    team_id: str = Field(description="Yahoo team ID")

    @field_validator("league_id")
    @classmethod
    def validate_league_id(cls, v: str) -> str:
        """Validate that league_id is not empty and can be converted to int."""
        if not v or not v.strip():
            raise ValueError("league_id cannot be empty. User must complete onboarding first.")
        try:
            int(v)
        except ValueError:
            raise ValueError(f"league_id must be a valid number, got: {v}") from None
        return v

    @field_validator("team_id")
    @classmethod
    def validate_team_id(cls, v: str) -> str:
        """Validate that team_id is not empty."""
        if not v or not v.strip():
            raise ValueError("team_id cannot be empty. User must complete onboarding first.")
        return v


@tool(args_schema=GetRosterInput)
def get_roster(user_email: str, league_id: str, team_id: str) -> str:
    """
    Get the current roster for a fantasy team with player stats and positions.

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
        return f"Error fetching roster: {e}"
