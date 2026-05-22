"""Repository class for Yahoo user team records."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import DatabaseRow, Repository
from data.user_repository import UserRepository


class YahooUserTeamRepository(Repository):
    """Repository for managing Yahoo user team records."""

    def __init__(self, session: Session | None = None) -> None:
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
        user_id = UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)
        self.add_team_by_user_id(league_id, team_id, user_id, team_name)

    def add_team_by_user_id(
        self, league_id: str, team_id: str, user_id: UUID, team_name: str
    ) -> None:
        """Add a user's Yahoo Fantasy team by canonical user ID."""
        self.upsert(
            conflict_columns=["league_id", "team_id", "user_id"],
            league_id=league_id,
            team_id=team_id,
            user_id=user_id,
            team_name=team_name,
        )

    def get_user_teams(self, user_email: str) -> list[DatabaseRow]:
        """Get all teams for a user.

        Args:
            user_email: User's email address

        Returns:
            List of team records
        """
        return list(
            self.session.execute(
                text(
                    """
                    SELECT
                        yut.league_id,
                        yut.team_id,
                        ui.external_id AS user_email,
                        yut.team_name,
                        yut.created_at
                    FROM yahoo_user_teams yut
                    JOIN user_identities ui
                        ON ui.user_id = yut.user_id
                        AND ui.medium = :medium
                    WHERE ui.external_id = :user_email
                    """
                ),
                {"medium": Medium.EMAIL.value, "user_email": user_email},
            ).fetchall()
        )

    def get_user_teams_for_league(self, user_email: str, league_id: str) -> list[DatabaseRow]:
        """Get a user's team records for one league."""
        return list(
            self.session.execute(
                text(
                    """
                    SELECT
                        yut.league_id,
                        yut.team_id,
                        ui.external_id AS user_email,
                        yut.team_name,
                        yut.created_at
                    FROM yahoo_user_teams yut
                    JOIN user_identities ui
                        ON ui.user_id = yut.user_id
                        AND ui.medium = :medium
                    WHERE ui.external_id = :user_email
                        AND yut.league_id = :league_id
                    """
                ),
                {
                    "medium": Medium.EMAIL.value,
                    "user_email": user_email,
                    "league_id": league_id,
                },
            ).fetchall()
        )

    def get_user_teams_with_league_info(self, user_email: str) -> list[dict[str, str]]:
        """Get all teams for a user with league details.

        Joins yahoo_user_teams with yahoo_leagues to include league name and game key.

        Args:
            user_email: User's email address

        Returns:
            List of team dicts with keys: league_id, team_id, team_name, game_key, league_name

        Used by: context_validator.validate_context
        """
        result = self.session.execute(
            text(
                """
                SELECT
                    yut.league_id,
                    yut.team_id,
                    yut.team_name,
                    yl.game_key,
                    yl.league_name,
                    yl.league_type
                FROM yahoo_user_teams yut
                JOIN yahoo_leagues yl ON yut.league_id = yl.league_id
                JOIN user_identities ui
                    ON ui.user_id = yut.user_id
                    AND ui.medium = :medium
                WHERE ui.external_id = :user_email
                """
            ),
            {"medium": Medium.EMAIL.value, "user_email": user_email},
        ).fetchall()

        return [
            {
                "league_id": str(row[0]),
                "team_id": str(row[1]),
                "team_name": str(row[2]),
                "game_key": str(row[3]),
                "league_name": str(row[4]),
                "sport": str(row[5]),
            }
            for row in result
        ]

    def get_user_teams_with_league_info_by_user_id(self, user_id: UUID) -> list[dict[str, str]]:
        """Get all teams for a canonical user with league details."""
        result = self.session.execute(
            text(
                """
                SELECT
                    yut.league_id,
                    yut.team_id,
                    yut.team_name,
                    yl.game_key,
                    yl.league_name,
                    yl.league_type
                FROM yahoo_user_teams yut
                JOIN yahoo_leagues yl ON yut.league_id = yl.league_id
                WHERE yut.user_id = :user_id
                """
            ),
            {"user_id": user_id},
        ).fetchall()

        return [
            {
                "league_id": str(row[0]),
                "team_id": str(row[1]),
                "team_name": str(row[2]),
                "game_key": str(row[3]),
                "league_name": str(row[4]),
                "sport": str(row[5]),
            }
            for row in result
        ]

    def get_team(self, league_id: str, team_id: str) -> DatabaseRow | None:
        """Get a specific team.

        Args:
            league_id: Yahoo Fantasy league ID
            team_id: Yahoo Fantasy team ID

        Returns:
            Team record or None if not found
        """
        return self.get_by(league_id=league_id, team_id=team_id)
