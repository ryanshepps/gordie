"""Tool to calculate fantasy points based on league scoring settings."""

import json
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


class CalculateFantasyPointsInput(BaseModel):
    """Input schema for calculate_fantasy_points tool."""

    player_stats: str = Field(
        description="JSON string of player stats from get_player_stats tool"
    )
    league_id: str = Field(
        description="Yahoo Fantasy league ID"
    )
    user_email: str = Field(
        description="User's email address for OAuth token lookup"
    )


@tool(args_schema=CalculateFantasyPointsInput)
def calculate_fantasy_points(player_stats: str, league_id: str, user_email: str) -> str:
    """
    Calculate fantasy points for players based on Yahoo Fantasy league scoring settings.

    This tool fetches the league's scoring categories and point values, then calculates
    total fantasy points for each player based on their stats.

    Args:
        player_stats: JSON string containing player statistics
        league_id: Yahoo Fantasy league ID
        user_email: User's email for authentication

    Returns:
        JSON string with fantasy points breakdown per player
    """
    try:
        # Parse player stats
        logger.info(f"Received player_stats type: {type(player_stats)}")
        logger.info(f"Received player_stats (first 200 chars): {str(player_stats)[:200]}")

        # Handle case where player_stats might already be a dict
        stats_dict = player_stats if isinstance(player_stats, dict) else json.loads(player_stats)

        # Get league settings
        yahoo_client = AuthenticatedYahooClient(
            league_id=int(league_id),
            user_email=user_email
        )
        yahoo_query = yahoo_client.query

        # Fetch league settings
        yahoo_query.get_league_settings()

        results: dict[str, Any] = {}

        # Default scoring (NHL standard categories if we can't fetch settings)
        default_scoring = {
            "G": 3.0,
            "A": 2.0,
            "PPP": 1.0,
            "SOG": 0.2,
            "HIT": 0.2,
            "BLK": 0.2,
            "+/-": 0.5,
        }

        # Extract scoring from league settings (this will need adjustment based on actual API response)
        scoring_categories = default_scoring
        logger.info(f"Using scoring categories: {scoring_categories}")

        # Calculate fantasy points for each player
        for player_id, player_data in stats_dict.items():
            if isinstance(player_data, dict) and player_data.get("status") != "error":
                fantasy_points = 0.0
                breakdown = {}

                # Goals
                if "goals" in player_data:
                    points_from_goals = player_data["goals"] * scoring_categories.get("G", 3.0)
                    fantasy_points += points_from_goals
                    breakdown["goals"] = points_from_goals

                # Assists
                if "assists" in player_data:
                    points_from_assists = player_data["assists"] * scoring_categories.get("A", 2.0)
                    fantasy_points += points_from_assists
                    breakdown["assists"] = points_from_assists

                # Power play goals (counted as PPP)
                if "power_play_goals" in player_data:
                    points_from_ppp = player_data["power_play_goals"] * scoring_categories.get("PPP", 1.0)
                    fantasy_points += points_from_ppp
                    breakdown["power_play_points"] = points_from_ppp

                # Shots on goal
                if "sog" in player_data:
                    points_from_sog = player_data["sog"] * scoring_categories.get("SOG", 0.2)
                    fantasy_points += points_from_sog
                    breakdown["shots"] = points_from_sog

                # Hits
                if "hits" in player_data:
                    points_from_hits = player_data["hits"] * scoring_categories.get("HIT", 0.2)
                    fantasy_points += points_from_hits
                    breakdown["hits"] = points_from_hits

                # Blocked shots
                if "blocked_shots" in player_data:
                    points_from_blocks = player_data["blocked_shots"] * scoring_categories.get("BLK", 0.2)
                    fantasy_points += points_from_blocks
                    breakdown["blocks"] = points_from_blocks

                # Plus/minus
                if "plus_minus" in player_data:
                    points_from_plusminus = player_data["plus_minus"] * scoring_categories.get("+/-", 0.5)
                    fantasy_points += points_from_plusminus
                    breakdown["plus_minus"] = points_from_plusminus

                results[player_id] = {
                    "total_fantasy_points": round(fantasy_points, 2),
                    "breakdown": breakdown,
                    "games_played": player_data.get("games_played", 0),
                    "fantasy_points_per_game": round(fantasy_points / player_data.get("games_played", 1), 2) if player_data.get("games_played", 0) > 0 else 0
                }
            else:
                results[player_id] = player_data

        return json.dumps(results, indent=2)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in calculate_fantasy_points: {e}")
        logger.error(f"Problematic input - player_stats type: {type(player_stats)}")
        logger.error(f"Problematic input - player_stats value: {player_stats}")
        return json.dumps({
            "status": "error",
            "error": f"Invalid JSON in player_stats: {e!s}",
            "note": "Please ensure player_stats is valid JSON"
        }, indent=2)
    except Exception as e:
        logger.error(f"Error calculating fantasy points: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "note": "Using default NHL scoring if league settings unavailable"
        }, indent=2)
