"""Repository class for NHL player game statistics."""

from typing import Any

from sqlalchemy.orm import Session

from data.repository import Repository


class NHLPlayerStatsRepository(Repository):
    """Repository for managing NHL player per-game statistics.

    This repository works with the nhl_player_game_stats table which stores
    box score data for each game a player plays in.

    For aggregate season statistics (xGoals, Fenwick%, etc.), use the
    MoneyPuck client instead which fetches data directly from MoneyPuck.com.
    """

    def __init__(self, session: Session | None = None):
        """Initialize NHL player stats repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("nhl_player_game_stats", session)

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
    ) -> tuple[Any, ...] | None:
        """Get stats for a specific player in a specific game.

        Args:
            nhl_api_player_id: NHL API player ID
            nhl_api_game_id: NHL API game ID

        Returns:
            Stats record or None if not found
        """
        return self.get_by(nhl_api_player_id=nhl_api_player_id, nhl_api_game_id=nhl_api_game_id)

    def get_player_games(self, nhl_api_player_id: int) -> list[tuple[Any, ...]]:
        """Get all game stats for a player.

        Args:
            nhl_api_player_id: NHL API player ID

        Returns:
            List of stats records
        """
        return self.get_all(nhl_api_player_id=nhl_api_player_id)
