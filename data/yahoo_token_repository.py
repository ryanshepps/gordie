"""Repository class for Yahoo OAuth token records."""

from typing import Any

import duckdb

from client.duck_db_client import get_platform_db_connection
from data.repository import Repository


class YahooTokenRepository(Repository):
    """Repository for managing Yahoo OAuth token records."""

    def __init__(self, conn: duckdb.DuckDBPyConnection | None = None):
        """Initialize Yahoo token repository.

        Args:
            conn: Optional database connection. If not provided, creates new platform connection.
        """
        self._owns_conn = conn is None
        self.conn = conn or get_platform_db_connection()
        super().__init__(self.conn, "yahoo_tokens")

    def save_token(
        self,
        user_email: str,
        yahoo_email: str,
        access_token: str,
        refresh_token: str,
        token_time: str,
        token_type: str = "Bearer",
    ) -> None:
        """Save or update Yahoo OAuth tokens for a user.

        Args:
            user_email: User's email address
            yahoo_email: Yahoo email address
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_time: Timestamp when token was issued
            token_type: Token type (default: "Bearer")
        """
        self.upsert(
            ["user_email"],
            user_email=user_email,
            yahoo_email=yahoo_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_time=token_time,
            token_type=token_type,
        )

    def get_token(self, user_email: str) -> tuple[Any, ...] | None:
        """Get OAuth tokens for a user.

        Args:
            user_email: User's email address

        Returns:
            Token record or None if not found
        """
        return self.get_by(user_email=user_email)

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_conn and self.conn:
            self.conn.close()
