"""Repository class for Yahoo user team records."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repository import Repository


class YahooUserTeamRepository(Repository):
    """Repository for managing Yahoo user team records."""

    def __init__(self, session: Session | None = None):
        """Initialize Yahoo user team repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("yahoo_user_teams", session)

    def add_team(self, league_id: str, team_id: str, user_email: str, team_name: str) -> None:
        """Add a user's Yahoo Fantasy team.

        Args:
            league_id: Yahoo Fantasy league ID
            team_id: Yahoo Fantasy team ID
            user_email: User's email address
            team_name: Name of the team
        """
        self.insert(
            league_id=league_id,
            team_id=team_id,
            user_email=user_email,
            team_name=team_name,
        )

    def get_user_teams(self, user_email: str) -> list[tuple[Any, ...]]:
        """Get all teams for a user.

        Args:
            user_email: User's email address

        Returns:
            List of team records
        """
        return self.get_all(user_email=user_email)

    def get_user_teams_with_league_info(self, user_email: str) -> list[dict[str, str]]:
        """Get all teams for a user with league details.

        Joins yahoo_user_teams with yahoo_leagues to include league name and game key.

        Args:
            user_email: User's email address

        Returns:
            List of team dicts with keys: league_id, team_id, team_name, game_key, league_name

        Used by: context_validator.validate_and_build_system_message
        """
        result = self.session.execute(
            text(
                """
                SELECT
                    yut.league_id,
                    yut.team_id,
                    yut.team_name,
                    yl.game_key,
                    yl.league_name
                FROM yahoo_user_teams yut
                JOIN yahoo_leagues yl ON yut.league_id = yl.league_id
                WHERE yut.user_email = :user_email
                """
            ),
            {"user_email": user_email},
        ).fetchall()

        return [
            {
                "league_id": str(row[0]),
                "team_id": str(row[1]),
                "team_name": str(row[2]),
                "game_key": str(row[3]),
                "league_name": str(row[4]),
            }
            for row in result
        ]

    def get_team(self, league_id: str, team_id: str) -> tuple[Any, ...] | None:
        """Get a specific team.

        Args:
            league_id: Yahoo Fantasy league ID
            team_id: Yahoo Fantasy team ID

        Returns:
            Team record or None if not found
        """
        return self.get_by(league_id=league_id, team_id=team_id)
