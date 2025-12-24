"""Tool to find undervalued players with strong underlying stats but lower Yahoo ranks."""

import json
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.player_comparison.get_comprehensive_player_stats import (
    get_comprehensive_player_stats_internal,
)
from tools.yahoo.find_similar_ranked_players import find_similar_ranked_players_internal

logger = get_logger(__name__)


class FindUndervaluedPlayersInput(BaseModel):
    """Input schema for find_undervalued_players tool."""

    user_email: str = Field(description="User's email address for Yahoo authentication")
    league_id: str = Field(description="Yahoo fantasy league ID")
    position: str = Field(
        default="",
        description="Optional position filter (e.g., 'C', 'LW', 'RW', 'D', 'G', 'F')",
    )
    min_rank: int = Field(
        default=50,
        description="Minimum Yahoo rank to search (lower = better ranked). Default 50 to skip elite players.",
    )
    max_rank: int = Field(
        default=200,
        description="Maximum Yahoo rank to search. Default 200 to find mid-tier undervalued players.",
    )
    min_undervalued_score: float = Field(
        default=3.0,
        description="Minimum undervalued score to include. Higher = more undervalued. Default 3.0.",
    )
    exclude_my_team_id: str = Field(
        default="",
        description="Optional team ID to exclude from results (your team)",
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of players to return. Default 10.",
    )


@tool(args_schema=FindUndervaluedPlayersInput)
def find_undervalued_players(
    user_email: str,
    league_id: str,
    position: str = "",
    min_rank: int = 50,
    max_rank: int = 200,
    min_undervalued_score: float = 3.0,
    exclude_my_team_id: str = "",
    max_results: int = 10,
) -> str:
    """
    Find players with strong underlying stats but lower Yahoo ranks - ideal trade targets.

    This tool identifies players who are undervalued based on:
    - High xGoals but low actual goals (due for positive regression)
    - Strong Fenwick%/Corsi% (good possession, sustainable production)
    - High TOI on good teams but underperforming in fantasy points
    - Top line deployment not yet reflected in rank
    - Favorable upcoming schedule

    The undervalued_score combines all these factors:
    - Score > 5: Highly undervalued, strong buy candidate
    - Score 3-5: Moderately undervalued, good trade target
    - Score 0-3: Fairly valued
    - Score < 0: Overvalued, avoid or sell

    Args:
        user_email: User's email for Yahoo OAuth
        league_id: Yahoo fantasy league ID
        position: Optional position filter (C, LW, RW, D, G, F)
        min_rank: Minimum rank to search (default 50 to skip elite players)
        max_rank: Maximum rank to search (default 200)
        min_undervalued_score: Minimum score to include (default 3.0)
        exclude_my_team_id: Team ID to exclude (your team)
        max_results: Maximum players to return (default 10)

    Returns:
        JSON with undervalued players sorted by undervalued_score (highest first).
        Each player includes full stats and reasons for their undervalued score.
    """
    try:
        # Step 1: Get players in the rank range from Yahoo
        target_rank = (min_rank + max_rank) // 2
        rank_range = (max_rank - min_rank) // 2

        logger.info(
            f"Finding undervalued players: rank {min_rank}-{max_rank}, "
            f"position={position or 'all'}, min_score={min_undervalued_score}"
        )

        similar_response = find_similar_ranked_players_internal(
            user_email=user_email,
            league_id=league_id,
            target_rank=target_rank,
            position=position,
            rank_range=rank_range,
            only_rostered=True,
            exclude_my_team_id=exclude_my_team_id,
        )
        similar_data = json.loads(similar_response)

        if "error" in similar_data:
            return json.dumps(
                {
                    "status": "error",
                    "error": similar_data["error"],
                    "message": "Failed to fetch players from Yahoo",
                }
            )

        players = similar_data.get("players", [])
        if not players:
            return json.dumps(
                {
                    "status": "success",
                    "players": [],
                    "message": f"No players found in rank range {min_rank}-{max_rank}",
                }
            )

        # Step 2: Get comprehensive stats for all players (includes undervalued_score)
        player_names = [p["name"] for p in players if p.get("name") != "Unknown"]

        # Batch players to avoid overwhelming the API (max 20 at a time)
        batch_size = 20
        all_stats: dict[str, Any] = {}

        for i in range(0, len(player_names), batch_size):
            batch = player_names[i : i + batch_size]
            logger.info(f"Fetching stats for batch {i // batch_size + 1}: {len(batch)} players")

            stats_response = get_comprehensive_player_stats_internal(
                player_names=batch,
                user_email=user_email,
                league_id=league_id,
            )
            batch_stats = json.loads(stats_response)

            # Handle error response
            if batch_stats.get("status") == "error":
                logger.warning(f"Batch stats fetch failed: {batch_stats.get('error')}")
                continue

            all_stats.update(batch_stats)

        # Step 3: Filter and sort by undervalued_score
        undervalued_players = []

        for _player_name, stats in all_stats.items():
            if stats.get("status") != "success":
                continue

            score = stats.get("undervalued_score", 0)
            if score < min_undervalued_score:
                continue

            # Add ownership info from the Yahoo search results
            yahoo_player = next((p for p in players if p.get("name") == stats.get("name")), {})

            undervalued_players.append(
                {
                    "name": stats.get("name"),
                    "team": stats.get("team"),
                    "position": stats.get("position"),
                    "yahoo_rank": stats.get("yahoo_rank"),
                    "owner_team_name": stats.get("owner_team_name")
                    or yahoo_player.get("owner_team_name"),
                    "undervalued_score": score,
                    "undervalued_reasons": stats.get("undervalued_reasons", []),
                    # Key stats for quick reference
                    "games_played": stats.get("games_played"),
                    "points": stats.get("points"),
                    "points_per_game": stats.get("points_per_game"),
                    "goals": stats.get("goals"),
                    "x_goals": stats.get("x_goals"),
                    "goals_above_expected": stats.get("goals_above_expected"),
                    "fenwick_pct": stats.get("fenwick_pct"),
                    "corsi_pct": stats.get("corsi_pct"),
                    "toi_per_game_minutes": stats.get("toi_per_game_minutes"),
                    "estimated_line_number": stats.get("estimated_line_number"),
                    "games_remaining_this_week": stats.get("games_remaining_this_week"),
                    "games_next_week": stats.get("games_next_week"),
                    # Full stats available if needed
                    "full_stats": stats,
                }
            )

        # Sort by undervalued_score (highest first)
        undervalued_players.sort(key=lambda x: x["undervalued_score"], reverse=True)

        # Limit results
        undervalued_players = undervalued_players[:max_results]

        # Group by owner for trade targeting
        players_by_owner: dict[str, list[Any]] = {}
        for player in undervalued_players:
            owner = player.get("owner_team_name") or "Unknown"
            if owner not in players_by_owner:
                players_by_owner[owner] = []
            players_by_owner[owner].append(player)

        return json.dumps(
            {
                "status": "success",
                "players": undervalued_players,
                "players_by_owner": players_by_owner,
                "count": len(undervalued_players),
                "filters": {
                    "rank_range": {"min": min_rank, "max": max_rank},
                    "position": position or "all",
                    "min_undervalued_score": min_undervalued_score,
                },
                "message": (
                    f"Found {len(undervalued_players)} undervalued players "
                    f"(score >= {min_undervalued_score}) in rank range {min_rank}-{max_rank}"
                ),
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error finding undervalued players: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "message": "Failed to find undervalued players",
            }
        )
