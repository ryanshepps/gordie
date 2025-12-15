"""Tool to onboard a user's selected Yahoo Fantasy team to the database."""

import json

from langchain.tools import tool
from pydantic import BaseModel, Field
from server.email_service import EmailService

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from scripts.add_yahoo_league import add_yahoo_league
from scripts.add_yahoo_user_team import add_yahoo_user_team

logger = get_logger(__name__)


class OnboardUserTeamInput(BaseModel):
    user_email: str = Field(description="User's email address")
    game_key: str = Field(
        description="Yahoo Fantasy game key from get_user_leagues (e.g., 'nhl', 'nfl')"
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
    user_email: str, game_key: str, league_id: int, team_name: str, team_id: int
) -> str:
    """
    Onboard a user's selected Yahoo Fantasy team to the database.
    This will fetch league details and save both the league and the user's team.

    Args:
        user_email: User's email address
        game_key: Yahoo Fantasy game key from get_user_leagues (e.g., "nhl", "nfl")
        league_id: Yahoo Fantasy league ID from get_user_leagues (just the numeric ID, e.g., "26455")
        team_id: Yahoo Fantasy team ID from get_user_leagues (just the numeric team ID)

    Returns:
        Confirmation message about the saved team.
    """
    try:
        # Create client with just the numeric league_id
        yahoo_client = AuthenticatedYahooClient(user_email=user_email, league_id=league_id)
        yahoo_query = yahoo_client.query

        # Fetch league settings to get league details
        league_settings = yahoo_query.get_league_settings()
        league_name = (
            str(league_settings.name) if hasattr(league_settings, "name") else f"League {league_id}"
        )
        league_type = (
            str(league_settings.game_code) if hasattr(league_settings, "game_code") else "unknown"
        )

        # Save league to database
        # Convert Settings object to dict for JSON serialization
        settings_dict = (
            league_settings.to_json()
            if hasattr(league_settings, "to_json")
            else str(league_settings)
        )
        add_yahoo_league(
            league_id=league_id,
            game_key=game_key,
            league_name=league_name,
            league_type=league_type,
            league_settings=settings_dict
            if isinstance(settings_dict, str)
            else json.dumps(settings_dict),
        )
        logger.info(f"Saved league {league_name} ({league_id})")

        # Save user team to database
        add_yahoo_user_team(
            league_id=league_id, team_id=team_id, user_email=user_email, team_name=team_name
        )
        logger.info(f"Saved team {team_name} for user {user_email}")

        # Send confirmation email
        try:
            email_service = EmailService()
            email_service.send_email(
                to_email=user_email,
                subject="Welcome to Gordie AI - Your Team is Ready!",
                text_body=f"""Hi there!

Your team '{team_name}' in league '{league_name}' has been successfully onboarded to Gordie AI.

You can now start messaging me about your fantasy team!

- Gordie
""",
            )
            logger.info(f"Sent onboarding confirmation email to {user_email}")
        except Exception as e:
            logger.error(f"Failed to send onboarding email to {user_email}: {e}")
            # Don't fail the onboarding if email fails

        return f"Successfully saved your team '{team_name}' in league '{league_name}'! You're all set up and ready to roll."

    except Exception as e:
        logger.error(f"Error saving user team: {e}")
        return f"Error saving team: {e!s}"
