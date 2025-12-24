"""Tool to fetch player statistics from MoneyPuck.

MoneyPuck provides advanced NHL analytics including expected goals (xGoals),
Fenwick/Corsi percentages, and danger zone breakdowns.
"""

import json
from typing import cast

from pydantic import BaseModel, Field

from client.moneypuck_client import get_multiple_players_stats
from module.logger import get_logger

logger = get_logger(__name__)


class GetMoneyPuckStatsInput(BaseModel):
    """Input schema for get_moneypuck_stats tool."""

    player_ids: list[int] = Field(description="List of NHL API player IDs to fetch stats for")
    situation: str = Field(
        default="all",
        description=(
            "Game situation: 'all' (default), '5on5', '5on4' (power play), "
            "'4on5' (penalty kill), 'other'"
        ),
    )
    season: int = Field(
        default=2025,
        description="Starting year of the season (e.g., 2025 for 2025-2026 season)",
    )


# Key columns to include in output (subset of full data for readability)
OUTPUT_COLUMNS = [
    "playerId",
    "name",
    "team",
    "position",
    "games_played",
    "icetime",
    "I_F_goals",
    "I_F_primaryAssists",
    "I_F_secondaryAssists",
    "I_F_points",
    "I_F_shotsOnGoal",
    "I_F_xGoals",
    "onIce_xGoalsPercentage",
    "onIce_fenwickPercentage",
    "onIce_corsiPercentage",
    "I_F_highDangerShots",
    "I_F_highDangerGoals",
    "I_F_highDangerxGoals",
    "I_F_hits",
    "I_F_takeaways",
    "I_F_giveaways",
    "penalityMinutes",
    "gameScore",
]


def _safe_int(value: object, default: int = 0) -> int:
    """Safely convert a value to int."""
    if value is None:
        return default
    try:
        return int(cast(int | float | str, value))
    except (ValueError, TypeError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        return float(cast(int | float | str, value))
    except (ValueError, TypeError):
        return default


def _safe_str(value: object) -> str | None:
    """Safely convert a value to str or None."""
    if value is None:
        return None
    return str(value)


def _format_player_stats(row: dict[str, object]) -> dict[str, str | int | float | None]:
    """Format a player's stats for output."""
    # Calculate derived stats
    games: int = _safe_int(row.get("games_played", 0))
    icetime_seconds: float = _safe_float(row.get("icetime", 0))

    goals: int = _safe_int(row.get("I_F_goals", 0))
    primary_assists: int = _safe_int(row.get("I_F_primaryAssists", 0))
    secondary_assists: int = _safe_int(row.get("I_F_secondaryAssists", 0))
    points: int = _safe_int(row.get("I_F_points", 0))
    shots_on_goal: int = _safe_int(row.get("I_F_shotsOnGoal", 0))
    x_goals: float = _safe_float(row.get("I_F_xGoals", 0))
    on_ice_xgoals_pct: float = _safe_float(row.get("onIce_xGoalsPercentage", 0))
    fenwick_pct: float = _safe_float(row.get("onIce_fenwickPercentage", 0))
    corsi_pct: float = _safe_float(row.get("onIce_corsiPercentage", 0))
    high_danger_shots: int = _safe_int(row.get("I_F_highDangerShots", 0))
    high_danger_goals: int = _safe_int(row.get("I_F_highDangerGoals", 0))
    high_danger_x_goals: float = _safe_float(row.get("I_F_highDangerxGoals", 0))
    hits: int = _safe_int(row.get("I_F_hits", 0))
    takeaways: int = _safe_int(row.get("I_F_takeaways", 0))
    giveaways: int = _safe_int(row.get("I_F_giveaways", 0))
    pim: int = _safe_int(row.get("penalityMinutes", 0))
    game_score: float = _safe_float(row.get("gameScore", 0))

    formatted: dict[str, str | int | float | None] = {
        "player_id": _safe_int(row.get("playerId")),
        "name": _safe_str(row.get("name")),
        "team": _safe_str(row.get("team")),
        "position": _safe_str(row.get("position")),
        "games_played": games,
        "toi_minutes": round(icetime_seconds / 60, 1) if icetime_seconds else 0,
        "toi_per_game_minutes": round(icetime_seconds / 60 / games, 1) if games > 0 else 0,
        # Scoring
        "goals": goals,
        "primary_assists": primary_assists,
        "secondary_assists": secondary_assists,
        "points": points,
        "shots_on_goal": shots_on_goal,
        # Advanced - xGoals
        "x_goals": round(x_goals, 2),
        "goals_above_expected": round(goals - x_goals, 2),
        # Advanced - percentages (already 0-1, convert to percentage)
        "on_ice_xgoals_pct": round(on_ice_xgoals_pct * 100, 1),
        "fenwick_pct": round(fenwick_pct * 100, 1),
        "corsi_pct": round(corsi_pct * 100, 1),
        # Danger zone
        "high_danger_shots": high_danger_shots,
        "high_danger_goals": high_danger_goals,
        "high_danger_x_goals": round(high_danger_x_goals, 2),
        # Other
        "hits": hits,
        "takeaways": takeaways,
        "giveaways": giveaways,
        "pim": pim,
        "game_score": round(game_score, 2),
    }

    # Add per-game rates if games > 0
    if games > 0:
        formatted["goals_per_game"] = round(goals / games, 2)
        formatted["points_per_game"] = round(points / games, 2)
        formatted["x_goals_per_game"] = round(x_goals / games, 2)
        formatted["shots_per_game"] = round(shots_on_goal / games, 2)

    return formatted


def get_moneypuck_stats(
    player_ids: list[int],
    situation: str = "all",
    season: int = 2024,
) -> str:
    """
    Fetch advanced player statistics from MoneyPuck.

    MoneyPuck provides analytics not available from the NHL API including:
    - Expected Goals (xGoals): Probability-weighted shot quality metric
    - Fenwick %: Unblocked shot attempt share (shots + missed shots)
    - Corsi %: Total shot attempt share (shots + missed + blocked)
    - High/Medium/Low danger shot breakdowns
    - Game Score: Composite player rating

    Data is cached for 1 hour to minimize API calls.

    Args:
        player_ids: List of NHL API player IDs
        situation: Game situation filter (all, 5on5, 5on4, 4on5, other)
        season: Starting year of season (e.g., 2024 for 2024-25)

    Returns:
        JSON string with player statistics including advanced metrics
    """
    results = {}

    try:
        df = get_multiple_players_stats(player_ids, situation=situation, season=season)

        for player_id in player_ids:
            player_df = df[df["playerId"] == player_id]

            if player_df.empty:
                logger.warning(
                    f"Player {player_id} not found in MoneyPuck {season}-{season + 1} data"
                )
                results[str(player_id)] = {
                    "status": "not_found",
                    "message": (
                        f"No MoneyPuck data found for player {player_id} "
                        f"in {season}-{season + 1} season"
                    ),
                }
                continue

            # Get the first (should be only) row for this player/situation
            row = player_df.iloc[0].to_dict()
            results[str(player_id)] = {
                "status": "success",
                "situation": situation,
                "season": f"{season}-{season + 1}",
                "stats": _format_player_stats(row),
            }

    except Exception as e:
        logger.error(f"Error fetching MoneyPuck stats: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "message": "Failed to fetch MoneyPuck data. Service may be unavailable.",
            }
        )

    return json.dumps(results, indent=2)
