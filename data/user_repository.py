"""Repository class for user records."""


import duckdb

from client.duck_db_client import get_platform_db_connection
from data.repository import Repository


class UserRepository(Repository):
    """Repository for managing user records."""

    def __init__(self, conn: duckdb.DuckDBPyConnection | None = None):
        """Initialize user repository.

        Args:
            conn: Optional database connection. If not provided, creates new platform connection.
        """
        self._owns_conn = conn is None
        self.conn = conn or get_platform_db_connection()
        super().__init__(self.conn, "users")

    def add_user(self, email: str) -> None:
        """Add a new user.

        Args:
            email: User's email address
        """
        self.insert(email=email)

    def get_user(self, email: str) -> tuple | None:
        """Get a user by email.

        Args:
            email: User's email address

        Returns:
            User record or None if not found
        """
        return self.get_by(email=email)

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_conn and self.conn:
            self.conn.close()
