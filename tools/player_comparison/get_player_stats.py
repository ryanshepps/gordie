"""Tool to fetch player statistics for configurable time periods."""

import json
from datetime import datetime, timedelta
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from data.nhl_player_stats_repository import NHLPlayerStatsRepository
from module.logger import get_logger

logger = get_logger(__name__)


class GetPlayerStatsInput(BaseModel):
    """Input schema for get_player_stats tool."""

    player_ids: list[int] = Field(
        description="List of NHL API player IDs to fetch stats for"
    )
    time_period: str = Field(
        default="last_10_games",
        description="Time period: 'last_5_games', 'last_10_games', 'last_20_games', 'season', 'last_30_days'"
    )


@tool(args_schema=GetPlayerStatsInput)
def get_player_stats(player_ids: list[int], time_period: str = "last_10_games") -> str:
    """
    Fetch aggregated player statistics for a configurable time period.

    This tool queries the NHL player stats database and aggregates statistics
    based on the specified time period. Supports various time ranges including
    last N games, last 30 days, or full season.

    Args:
        player_ids: List of NHL API player IDs
        time_period: Time period for stats aggregation

    Returns:
        JSON string with aggregated player statistics
    """
    repo = NHLPlayerStatsRepository()
    results: dict[str, Any] = {}

    try:
        for player_id in player_ids:
            try:
                logger.info(f"Fetching stats for player_id: {player_id}, period: {time_period}")

                # Build query based on time period
                if time_period == "season":
                    query = """
                        SELECT * FROM nhl_player_stats
                        WHERE nhl_api_player_id = ?
                        ORDER BY game_date DESC
                    """
                    params = [player_id]
                elif time_period.startswith("last_") and time_period.endswith("_games"):
                    num_games = int(time_period.split("_")[1])
                    query = f"""
                        SELECT * FROM nhl_player_stats
                        WHERE nhl_api_player_id = ?
                        ORDER BY game_date DESC
                        LIMIT {num_games}
                    """
                    params = [player_id]
                elif time_period == "last_30_days":
                    cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                    query = """
                        SELECT * FROM nhl_player_stats
                        WHERE nhl_api_player_id = ?
                        AND game_date >= ?
                        ORDER BY game_date DESC
                    """
                    params = [player_id, cutoff_date]
                else:
                    raise ValueError(f"Unsupported time period: {time_period}")

                games = repo.conn.execute(query, params).fetchall()

                if not games:
                    results[str(player_id)] = {
                        "status": "no_data",
                        "message": f"No stats found for player {player_id} in period {time_period}"
                    }
                    continue

                # Aggregate stats
                # Column indices based on schema:
                # 0: nhl_api_player_id, 1: nhl_api_game_id, 2: game_date
                # 3: full_name, 4: first_name, 5: last_name
                # 6: goals, 7: assists, 8: points, 9: plus_minus, 10: pim
                # 11: hits, 12: power_play_goals, 13: sog, 14: faceoff_winning_pctg
                # 15: toi, 16: blocked_shots, 17: shifts
                # 18: giveaways, 19: takeaways, 20: corsi_for, 21: fenwick_for, 22: missed_shots
                stats = {
                    "player_id": player_id,
                    "games_played": len(games),
                    "time_period": time_period,
                    "goals": sum(g[6] or 0 for g in games),
                    "assists": sum(g[7] or 0 for g in games),
                    "points": sum(g[8] or 0 for g in games),
                    "plus_minus": sum(g[9] or 0 for g in games),
                    "pim": sum(g[10] or 0 for g in games),
                    "hits": sum(g[11] or 0 for g in games),
                    "power_play_goals": sum(g[12] or 0 for g in games),
                    "sog": sum(g[13] or 0 for g in games),
                    "blocked_shots": sum(g[16] or 0 for g in games),
                    "shifts": sum(g[17] or 0 for g in games),
                    "giveaways": sum(g[18] or 0 for g in games),
                    "takeaways": sum(g[19] or 0 for g in games),
                    "corsi_for": sum(g[20] or 0 for g in games),
                    "fenwick_for": sum(g[21] or 0 for g in games),
                    "missed_shots": sum(g[22] or 0 for g in games),
                    "avg_faceoff_winning_pctg": float(sum(g[14] or 0 for g in games) / len(games)) if games else 0.0,
                }

                # Calculate per-game averages
                games_played = int(stats["games_played"])
                if games_played > 0:
                    stats["goals_per_game"] = float(stats["goals"]) / games_played
                    stats["assists_per_game"] = float(stats["assists"]) / games_played
                    stats["points_per_game"] = float(stats["points"]) / games_played
                    stats["sog_per_game"] = float(stats["sog"]) / games_played
                    stats["hits_per_game"] = float(stats["hits"]) / games_played

                results[str(player_id)] = stats

            except Exception as e:
                logger.error(f"Error fetching stats for player {player_id}: {e}")
                results[str(player_id)] = {
                    "status": "error",
                    "error": str(e)
                }
    finally:
        repo.close()

    return json.dumps(results, indent=2)
