"""Repository class for Yahoo league records."""

from typing import Any

from sqlalchemy.orm import Session

from data.repository import Repository


class YahooLeagueRepository(Repository):
    """Repository for managing Yahoo league records."""

    def __init__(self, session: Session | None = None):
        """Initialize Yahoo league repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("yahoo_leagues", session)

    def add_league(
        self,
        league_id: str,
        game_key: str,
        league_name: str,
        league_type: str,
        league_settings: str,
    ) -> None:
        """Add a Yahoo Fantasy league.

        Args:
            league_id: Yahoo Fantasy league ID (e.g., "nhl.l.12345")
            game_key: Yahoo Fantasy game key (e.g., "nhl")
            league_name: Name of the league
            league_type: Type of league (e.g., "nhl", "nfl")
            league_settings: JSON string of league settings
        """
        self.upsert(
            ["league_id"],
            league_id=league_id,
            game_key=game_key,
            league_name=league_name,
            league_type=league_type,
            league_settings=league_settings,
        )

    def get_league(self, league_id: str) -> tuple[Any, ...] | None:
        """Get a league by ID.

        Args:
            league_id: Yahoo Fantasy league ID

        Returns:
            League record or None if not found
        """
        return self.get_by(league_id=league_id)
