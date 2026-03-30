"""Tool for multi-dimensional player comparison with weighted scoring."""

import json
from typing import Any, cast

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)


class ComparePlayersInput(BaseModel):
    """Input schema for compare_players_comprehensive tool."""

    player_stats: str = Field(description="JSON string of player stats from query_stats_db tool")
    fantasy_points: str = Field(
        description="JSON string of fantasy points from calculate_fantasy_points tool"
    )
    player_positions: str = Field(
        default="{}", description="JSON string mapping player_id to position (F/D/G)"
    )


def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value to 0-100 scale."""
    if max_val == min_val:
        return 50.0
    return ((value - min_val) / (max_val - min_val)) * 100


@tool(args_schema=ComparePlayersInput)
def compare_players_comprehensive(
    player_stats: str, fantasy_points: str, player_positions: str = "{}"
) -> str:
    """
    Perform multi-dimensional player comparison with weighted scoring.

    Compares players across 4 dimensions:
    - Fantasy Points (30%): Based on league scoring settings
    - General Performance (25%): Goals, assists, points, SOG
    - Position-Specific (25%): Different metrics for forwards vs defense
    - Recent Trend (20%): Performance momentum

    Args:
        player_stats: JSON string with player statistics
        fantasy_points: JSON string with fantasy point calculations
        player_positions: JSON string mapping player IDs to positions

    Returns:
        JSON string with comprehensive comparison and recommendation
    """
    try:
        # Handle cases where inputs might already be dicts
        if isinstance(player_stats, dict):
            stats_dict: dict[str, Any] = player_stats
        else:
            stats_dict = json.loads(player_stats)

        fantasy_dict: dict[str, Any]
        if isinstance(fantasy_points, dict):
            fantasy_dict = fantasy_points
        else:
            fantasy_dict = json.loads(fantasy_points)

        positions_dict: dict[str, Any]
        if isinstance(player_positions, dict):
            positions_dict = player_positions
        elif player_positions:
            positions_dict = json.loads(player_positions)
        else:
            positions_dict = {}

        if not stats_dict or not fantasy_dict:
            return json.dumps({"status": "error", "message": "Missing required input data"})

        # Filter out error entries
        valid_players: list[str] = []
        for pid in stats_dict:
            player_data = cast(Any, stats_dict)[str(pid)]
            if isinstance(player_data, dict) and player_data.get("status") != "error":
                valid_players.append(str(pid))

        if len(valid_players) < 2:
            return json.dumps(
                {"status": "error", "message": "Need at least 2 valid players to compare"}
            )

        player_scores: dict[str, dict[str, float]] = {}

        # Calculate scores for each player
        for player_id in valid_players:
            stats: dict[str, Any] = cast(Any, stats_dict)[player_id]
            fantasy: dict[str, Any] = cast(dict[str, Any], fantasy_dict.get(player_id, {}))
            position: str = str(positions_dict.get(player_id, "F"))

            scores: dict[str, float] = {}

            # 1. Fantasy Score (30% weight)
            fantasy_pts = fantasy.get("total_fantasy_points", 0)
            scores["fantasy"] = fantasy_pts

            # 2. General Performance Score (25% weight)
            ppg = stats.get("points_per_game", 0)
            gpg = stats.get("goals_per_game", 0)
            sog_pg = stats.get("sog_per_game", 0)
            plus_minus = stats.get("plus_minus", 0)

            general_score = (ppg * 40) + (gpg * 25) + (sog_pg * 5) + (plus_minus * 0.5)
            scores["general"] = general_score

            # 3. Position-Specific Score (25% weight)
            if position in ["F", "C", "LW", "RW"]:  # Forwards
                position_score = (
                    (gpg * 35) + (ppg * 25) + (sog_pg * 5) + (stats.get("takeaways", 0) * 0.5)
                )
            else:  # Defense
                apg = stats.get("assists_per_game", 0)
                blocks_pg = stats.get("blocked_shots", 0) / stats.get("games_played", 1)
                position_score = (
                    (apg * 30) + (blocks_pg * 2) + (plus_minus * 0.5) + (stats.get("hits", 0) * 0.2)
                )

            scores["position_specific"] = position_score

            # 4. Trend Score (20% weight) - placeholder for now
            # Would need last 5 games vs season average comparison
            scores["trend"] = 50.0  # Neutral score

            player_scores[player_id] = scores

        # Normalize and weight scores
        final_scores: dict[str, float] = {}

        for player_id in valid_players:
            scores = player_scores[player_id]

            # Get min/max for normalization
            fantasy_vals = [player_scores[p]["fantasy"] for p in valid_players]
            general_vals = [player_scores[p]["general"] for p in valid_players]
            position_vals = [player_scores[p]["position_specific"] for p in valid_players]

            # Normalize to 0-100
            fantasy_norm = normalize_score(scores["fantasy"], min(fantasy_vals), max(fantasy_vals))
            general_norm = normalize_score(scores["general"], min(general_vals), max(general_vals))
            position_norm = normalize_score(
                scores["position_specific"], min(position_vals), max(position_vals)
            )
            trend_norm = scores["trend"]

            # Apply weights
            total_score = (
                (fantasy_norm * 0.30)
                + (general_norm * 0.25)
                + (position_norm * 0.25)
                + (trend_norm * 0.20)
            )

            final_scores[player_id] = round(total_score, 2)

        # Determine winner
        winner_id = max(final_scores.keys(), key=lambda k: final_scores[k])

        # Build comparison data
        comparison_data: dict[str, Any] = {
            "recommendation": winner_id,
            "confidence": (
                "High" if final_scores[winner_id] - min(final_scores.values()) > 10 else "Medium"
            ),
            "overall_scores": final_scores,
            "category_breakdown": {},
            "key_differentiators": [],
            "stats_comparison": {},
        }

        # Add detailed breakdown
        for player_id in valid_players:
            stats: dict[str, Any] = cast(Any, stats_dict)[player_id]
            fantasy: dict[str, Any] = cast(dict[str, Any], fantasy_dict.get(player_id, {}))
            scores = player_scores[player_id]

            comparison_data["category_breakdown"][player_id] = {
                "fantasy_points": round(scores["fantasy"], 2),
                "general_performance": round(scores["general"], 2),
                "position_specific": round(scores["position_specific"], 2),
                "recent_trend": round(scores["trend"], 2),
            }

            comparison_data["stats_comparison"][player_id] = {
                "games_played": stats.get("games_played", 0),
                "goals": stats.get("goals", 0),
                "assists": stats.get("assists", 0),
                "points": stats.get("points", 0),
                "ppg": stats.get("points_per_game", 0),
                "sog": stats.get("sog", 0),
                "hits": stats.get("hits", 0),
                "blocks": stats.get("blocked_shots", 0),
                "plus_minus": stats.get("plus_minus", 0),
                "fantasy_points": fantasy.get("total_fantasy_points", 0),
            }

        # Generate key differentiators
        winner_stats: dict[str, Any] = cast(Any, stats_dict)[winner_id]
        for other_id in valid_players:
            if other_id != winner_id:
                other_stats: dict[str, Any] = cast(Any, stats_dict)[other_id]

                winner_ppg = winner_stats.get("points_per_game", 0)
                other_ppg = other_stats.get("points_per_game", 0)
                ppg_diff = winner_ppg - other_ppg
                if abs(ppg_diff) > 0.2:
                    comparison_data["key_differentiators"].append(
                        f"Player {winner_id} has {ppg_diff:+.2f} higher PPG"
                    )

                sog_diff = winner_stats.get("sog", 0) - other_stats.get("sog", 0)
                if abs(sog_diff) > 10:
                    comparison_data["key_differentiators"].append(
                        f"Player {winner_id} has {sog_diff:+d} more shots"
                    )

        return json.dumps(comparison_data, indent=2)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in compare_players_comprehensive: {e}")
        logger.error(
            f"Input types - player_stats: {type(player_stats)}, "
            f"fantasy_points: {type(fantasy_points)}, "
            f"player_positions: {type(player_positions)}"
        )
        return json.dumps({"status": "error", "error": f"Invalid JSON in input: {e!s}"}, indent=2)
    except Exception as e:
        logger.error(f"Error in comprehensive comparison: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
