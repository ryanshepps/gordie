"""MoneyPuck client for fetching NHL advanced statistics.

This client fetches player statistics from MoneyPuck's publicly available CSV files.
Data is cached in memory to avoid repeated downloads within the same session.

MoneyPuck provides advanced analytics including:
- Expected Goals (xGoals)
- Fenwick and Corsi percentages
- High/Medium/Low danger shot breakdowns
- On-ice and off-ice metrics

Data is free for non-commercial use with attribution to MoneyPuck.com.
"""

import time
from io import StringIO
from typing import cast

import pandas as pd
import requests

from module.logger import get_logger

logger = get_logger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour cache
_cache: dict[str, tuple[pd.DataFrame, float]] = {}

# MoneyPuck CSV URLs
MONEYPUCK_BASE_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary"


def _get_skaters_url(season: int) -> str:
    """Get the URL for skater stats CSV.

    Args:
        season: Starting year of the season (e.g., 2024 for 2024-2025 season)

    Returns:
        URL string for the skaters CSV
    """
    return f"{MONEYPUCK_BASE_URL}/{season}/regular/skaters.csv"


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cached data is still valid."""
    if cache_key not in _cache:
        return False
    _, timestamp = _cache[cache_key]
    return (time.time() - timestamp) < CACHE_TTL_SECONDS


def fetch_skater_stats(season: int = 2024, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch skater statistics from MoneyPuck.

    Args:
        season: Starting year of the season (e.g., 2024 for 2024-2025)
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        DataFrame with all skater statistics

    Raises:
        requests.RequestException: If the download fails
    """
    cache_key = f"skaters_{season}"

    if not force_refresh and _is_cache_valid(cache_key):
        logger.debug(f"Using cached MoneyPuck data for {season}")
        return _cache[cache_key][0]

    url = _get_skaters_url(season)
    logger.info(f"Fetching MoneyPuck skater data from {url}")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))
    _cache[cache_key] = (df, time.time())

    logger.info(f"Fetched {len(df)} rows of skater data for {season} season")
    return df


def get_player_stats(
    player_id: int | None = None,
    player_name: str | None = None,
    situation: str = "all",
    season: int = 2024,
) -> pd.DataFrame:
    """Get statistics for a specific player.

    Args:
        player_id: NHL player ID (preferred)
        player_name: Player name for fuzzy matching (used if player_id not provided)
        situation: Game situation filter - 'all', '5on5', '5on4', '4on5', 'other'
        season: Starting year of the season

    Returns:
        DataFrame with player statistics (may have multiple rows for different situations)

    Raises:
        ValueError: If neither player_id nor player_name is provided
    """
    if player_id is None and player_name is None:
        raise ValueError("Either player_id or player_name must be provided")

    df = fetch_skater_stats(season)

    # Filter by situation
    if situation != "all_situations":
        df = df[df["situation"] == situation]

    # Filter by player
    if player_id is not None:
        return df.loc[df["playerId"] == player_id]
    else:
        # Fuzzy match on name (case-insensitive contains)
        assert player_name is not None  # guaranteed by earlier check
        name_col = cast(pd.Series, df["name"]).astype(str)
        mask = name_col.str.lower().str.contains(player_name.lower(), na=False)
        return df.loc[mask]


def get_multiple_players_stats(
    player_ids: list[int],
    situation: str = "all",
    season: int = 2024,
) -> pd.DataFrame:
    """Get statistics for multiple players.

    Args:
        player_ids: List of NHL player IDs
        situation: Game situation filter
        season: Starting year of the season

    Returns:
        DataFrame with statistics for all requested players
    """
    df = fetch_skater_stats(season)

    # Filter by situation
    if situation != "all_situations":
        df = df[df["situation"] == situation]

    player_id_col = cast(pd.Series, df["playerId"])
    mask = player_id_col.isin(player_ids)
    return df.loc[mask]


def search_players(
    query: str,
    situation: str = "all",
    season: int = 2024,
    limit: int = 10,
) -> pd.DataFrame:
    """Search for players by name.

    Args:
        query: Search string (case-insensitive)
        situation: Game situation filter
        season: Starting year of the season
        limit: Maximum number of results

    Returns:
        DataFrame with matching players, sorted by games played
    """
    df = fetch_skater_stats(season)

    # Filter by situation
    if situation != "all_situations":
        df = df[df["situation"] == situation]

    # Search by name
    name_col = cast(pd.Series, df["name"]).astype(str)
    mask = name_col.str.lower().str.contains(query.lower(), na=False)
    matches = df.loc[mask]

    # Sort by games played and limit
    sorted_matches = matches.sort_values(by="games_played", ascending=False)
    return sorted_matches.head(limit)


def get_league_leaders(
    stat: str,
    situation: str = "all",
    season: int = 2024,
    limit: int = 10,
    min_games: int = 10,
    ascending: bool = False,
) -> pd.DataFrame:
    """Get league leaders for a specific statistic.

    Args:
        stat: Column name to rank by (e.g., 'I_F_xGoals', 'I_F_goals', 'onIce_fenwickPercentage')
        situation: Game situation filter
        season: Starting year of the season
        limit: Number of leaders to return
        min_games: Minimum games played filter
        ascending: If True, return lowest values first

    Returns:
        DataFrame with league leaders for the specified stat
    """
    df = fetch_skater_stats(season)

    # Filter by situation and minimum games
    if situation != "all_situations":
        df = df.loc[df["situation"] == situation]
    df = df.loc[df["games_played"] >= min_games]

    # Sort and limit
    sorted_df = df.sort_values(by=stat, ascending=ascending)
    return sorted_df.head(limit)


def clear_cache() -> None:
    """Clear the in-memory cache."""
    _cache.clear()
    logger.info("MoneyPuck cache cleared")


# Key statistics columns for easy reference
KEY_STATS = {
    # Identifiers
    "playerId": "NHL Player ID",
    "name": "Player name",
    "team": "Team abbreviation",
    "position": "Position (L, C, R, D)",
    "situation": "Game situation (all, 5on5, 5on4, 4on5, other)",
    # Basic stats
    "games_played": "Games played",
    "icetime": "Ice time in seconds",
    "I_F_goals": "Goals",
    "I_F_primaryAssists": "Primary assists",
    "I_F_secondaryAssists": "Secondary assists",
    "I_F_points": "Points (goals + assists)",
    "I_F_shotsOnGoal": "Shots on goal",
    # Advanced stats
    "I_F_xGoals": "Expected goals",
    "I_F_flurryAdjustedxGoals": "Flurry-adjusted expected goals",
    "onIce_xGoalsPercentage": "On-ice xGoals percentage",
    "onIce_fenwickPercentage": "On-ice Fenwick percentage",
    "onIce_corsiPercentage": "On-ice Corsi percentage",
    # Danger zone stats
    "I_F_highDangerShots": "High danger shots",
    "I_F_highDangerGoals": "High danger goals",
    "I_F_highDangerxGoals": "High danger expected goals",
    "I_F_mediumDangerShots": "Medium danger shots",
    "I_F_lowDangerShots": "Low danger shots",
    # Other
    "I_F_hits": "Hits",
    "I_F_takeaways": "Takeaways",
    "I_F_giveaways": "Giveaways",
    "penalityMinutes": "Penalty minutes",
    "I_F_faceOffsWon": "Faceoffs won",
    "gameScore": "Game Score rating",
}
