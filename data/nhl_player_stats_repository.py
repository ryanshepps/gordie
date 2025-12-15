"""Repository class for NHL player statistics."""


import duckdb

from client.duck_db_client import get_nhl_stats_db_connection
from data.repository import Repository


class NHLPlayerStatsRepository(Repository):
    """Repository for managing NHL player statistics."""

    def __init__(self, conn: duckdb.DuckDBPyConnection | None = None):
        """Initialize NHL player stats repository.

        Args:
            conn: Optional database connection. If not provided, creates new NHL stats connection.
        """
        self._owns_conn = conn is None
        self.conn = conn or get_nhl_stats_db_connection()
        super().__init__(self.conn, "nhl_player_stats")

    def add_stats(
        self,
        nhl_api_player_id: int,
        nhl_api_game_id: int,
        game_date: str,
        **stats,
    ) -> None:
        """Add NHL player statistics for a game.

        Args:
            nhl_api_player_id: NHL API player ID
            nhl_api_game_id: NHL API game ID
            game_date: Date of the game
            **stats: Additional stat fields (goals, assists, points, etc.)
        """
        self.insert(
            nhl_api_player_id=nhl_api_player_id,
            nhl_api_game_id=nhl_api_game_id,
            game_date=game_date,
            **stats,
        )

    def get_player_stats(
        self, nhl_api_player_id: int, nhl_api_game_id: int
    ) -> tuple | None:
        """Get stats for a specific player in a specific game.

        Args:
            nhl_api_player_id: NHL API player ID
            nhl_api_game_id: NHL API game ID

        Returns:
            Stats record or None if not found
        """
        return self.get_by(
            nhl_api_player_id=nhl_api_player_id, nhl_api_game_id=nhl_api_game_id
        )

    def get_player_games(self, nhl_api_player_id: int) -> list[tuple]:
        """Get all game stats for a player.

        Args:
            nhl_api_player_id: NHL API player ID

        Returns:
            List of stats records
        """
        return self.get_all(nhl_api_player_id=nhl_api_player_id)

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_conn and self.conn:
            self.conn.close()
