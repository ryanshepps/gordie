"""Repository class for Yahoo user team records."""

from typing import Any

import duckdb

from client.duck_db_client import get_platform_db_connection
from data.repository import Repository


class YahooUserTeamRepository(Repository):
    """Repository for managing Yahoo user team records."""

    def __init__(self, conn: duckdb.DuckDBPyConnection | None = None):
        """Initialize Yahoo user team repository.

        Args:
            conn: Optional database connection. If not provided, creates new platform connection.
        """
        self._owns_conn = conn is None
        self.conn = conn or get_platform_db_connection()
        super().__init__(self.conn, "yahoo_user_teams")

    def add_team(
        self, league_id: str, team_id: str, user_email: str, team_name: str
    ) -> None:
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

    def get_team(self, league_id: str, team_id: str) -> tuple[Any, ...] | None:
        """Get a specific team.

        Args:
            league_id: Yahoo Fantasy league ID
            team_id: Yahoo Fantasy team ID

        Returns:
            Team record or None if not found
        """
        return self.get_by(league_id=league_id, team_id=team_id)

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_conn and self.conn:
            self.conn.close()
