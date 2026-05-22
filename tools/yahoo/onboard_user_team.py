"""Tool to onboard a user's selected Yahoo Fantasy team to the database."""

import json
from typing import Annotated
from uuid import UUID

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field

from billing.tier import build_upgrade_message_by_user_id, check_league_limit_by_user_id
from client.authenticated_yahoo_client import AuthenticatedYahooClient
from data.yahoo_league_repository import YahooLeagueRepository
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.logger import get_logger
from tools.user_context import get_user_id

logger = get_logger(__name__)


class OnboardUserTeamInput(BaseModel):
    game_key: str = Field(
        description="Numeric Yahoo Fantasy game key from get_user_leagues (e.g., '423', '465')"
    )
    game_code: str = Field(
        description="Yahoo Fantasy sport code from get_user_leagues (e.g., 'nhl', 'mlb', 'nfl', 'nba')"
    )
    league_id: int = Field(
        description="Yahoo Fantasy league ID from get_user_leagues (just the numeric ID, e.g., '26455')"
    )
    team_name: str = Field(description="Yahoo Fantasy team name from get_user_leagues")
    team_id: int = Field(
        description="Yahoo Fantasy team ID from get_user_leagues (just the numeric team ID)"
    )


@tool(args_schema=OnboardUserTeamInput)
def onboard_user_team(
    game_key: str,
    game_code: str,
    league_id: int,
    team_name: str,
    team_id: int,
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """
    Onboard a user's selected Yahoo Fantasy team to the database.
    This will fetch league details and save both the league and the user's team.

    Args:
        game_key: Numeric Yahoo Fantasy game key from get_user_leagues (e.g., "423", "465")
        game_code: Yahoo Fantasy sport code (e.g., "nhl", "mlb", "nfl", "nba")
        league_id: Yahoo Fantasy league ID from get_user_leagues (just the numeric ID, e.g., "26455")
        team_id: Yahoo Fantasy team ID from get_user_leagues (just the numeric team ID)

    Returns:
        Confirmation message about the saved team.
    """
    user_id = get_user_id(state)
    allowed, reason = check_league_limit_by_user_id(user_id)
    if not allowed:
        return build_upgrade_message_by_user_id(user_id, reason, "email")

    try:
        yahoo_client = AuthenticatedYahooClient(
            user_id=user_id, league_id=league_id, game_code=game_code, game_key=game_key
        )
        yahoo_query = yahoo_client.query

        # Fetch league settings to get league details
        league_settings = yahoo_query.get_league_settings()
        league_name = (
            str(league_settings.name) if hasattr(league_settings, "name") else f"League {league_id}"
        )
        league_type = game_code

        # Save league to database
        # Convert Settings object to dict for JSON serialization
        settings_dict = (
            league_settings.to_json()
            if hasattr(league_settings, "to_json")
            else str(league_settings)
        )
        league_repo = YahooLeagueRepository()
        league_repo.add_league(
            league_id=str(league_id),
            game_key=game_key,
            league_name=league_name,
            league_type=league_type,
            league_settings=settings_dict
            if isinstance(settings_dict, str)
            else json.dumps(settings_dict),
        )
        league_repo.close()
        logger.info(f"Saved league {league_name} ({league_id})")

        # Save user team to database
        team_repo = YahooUserTeamRepository()
        team_repo.add_team_by_user_id(
            league_id=str(league_id),
            team_id=str(team_id),
            user_id=UUID(user_id),
            team_name=team_name,
        )
        team_repo.close()
        logger.info(f"Saved team {team_name} for user_id={user_id}")

        return f"Successfully saved your team '{team_name}' in league '{league_name}'! You're all set up and ready to roll."

    except Exception as e:
        logger.error(f"Error saving user team: {e}")
        return f"Error saving team: {e!s}"
