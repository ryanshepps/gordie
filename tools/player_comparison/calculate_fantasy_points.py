"""Tool to calculate fantasy points based on league scoring settings."""

import json
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


# Mapping from Yahoo stat display names to our internal stat keys
YAHOO_STAT_NAME_MAP = {
    "G": "goals",
    "A": "assists",
    "PIM": "pim",
    "+/-": "plus_minus",
    "PPG": "power_play_goals",
    "PPA": "power_play_assists",
    "PPP": "power_play_points",
    "SHG": "short_handed_goals",
    "SHA": "short_handed_assists",
    "SHP": "short_handed_points",
    "GWG": "game_winning_goals",
    "SOG": "sog",
    "HIT": "hits",
    "BLK": "blocked_shots",
    "FW": "faceoffs_won",
    "FL": "faceoffs_lost",
}


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


def extract_scoring_settings(settings) -> dict[str, float]:
    """
    Extract scoring settings from Yahoo league settings.

    Args:
        settings: Yahoo Settings object from get_league_settings()

    Returns:
        Dictionary mapping stat abbreviations to point values

    Raises:
        ValueError: If stat_modifiers is missing or empty
    """
    if not hasattr(settings, "stat_modifiers") or settings.stat_modifiers is None:
        raise ValueError("League settings missing stat_modifiers")

    stat_modifiers = settings.stat_modifiers
    if not hasattr(stat_modifiers, "stats") or not stat_modifiers.stats:
        raise ValueError("League stat_modifiers has no stats defined")

    scoring = {}
    for stat in stat_modifiers.stats:
        # stat.value contains the point value for this stat
        # stat.stat_id is the unique ID, but we need to map it to abbreviation
        # The stat object should have display_name or abbr from stat_categories
        if hasattr(stat, "value") and stat.value is not None:
            # Try to get the stat abbreviation
            abbr = getattr(stat, "abbr", None) or getattr(stat, "display_name", None)
            if abbr:
                scoring[abbr] = float(stat.value)

    if not scoring:
        raise ValueError("Could not extract any scoring categories from league settings")

    return scoring


def calculate_player_points(
    player_data: dict[str, Any],
    scoring: dict[str, float],
) -> dict[str, Any]:
    """
    Calculate fantasy points for a single player.

    Args:
        player_data: Player stats dictionary
        scoring: Scoring settings mapping stat abbr to point value

    Returns:
        Dictionary with total_fantasy_points, breakdown, games_played, fantasy_points_per_game
    """
    fantasy_points = 0.0
    breakdown = {}

    for yahoo_abbr, internal_key in YAHOO_STAT_NAME_MAP.items():
        if yahoo_abbr in scoring and internal_key in player_data:
            stat_value = player_data[internal_key]
            points = stat_value * scoring[yahoo_abbr]
            fantasy_points += points
            breakdown[internal_key] = points

    games_played = player_data.get("games_played", 0)
    points_per_game = (
        round(fantasy_points / games_played, 2) if games_played > 0 else 0
    )

    return {
        "total_fantasy_points": round(fantasy_points, 2),
        "breakdown": breakdown,
        "games_played": games_played,
        "fantasy_points_per_game": points_per_game,
    }


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
        logger.info(f"Received player_stats type: {type(player_stats)}")
        logger.info(f"Received player_stats (first 200 chars): {str(player_stats)[:200]}")

        # Parse player stats
        stats_dict = player_stats if isinstance(player_stats, dict) else json.loads(player_stats)

        # Get league settings from Yahoo
        yahoo_client = AuthenticatedYahooClient(
            league_id=int(league_id),
            user_email=user_email
        )
        settings = yahoo_client.query.get_league_settings()

        # Extract scoring settings - will raise ValueError if not available
        scoring = extract_scoring_settings(settings)
        logger.info(f"Extracted scoring categories from league: {scoring}")

        # Calculate fantasy points for each player
        results: dict[str, Any] = {}
        for player_id, player_data in stats_dict.items():
            if isinstance(player_data, dict) and player_data.get("status") != "error":
                results[player_id] = calculate_player_points(player_data, scoring)
            else:
                results[player_id] = player_data

        return json.dumps(results, indent=2)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in calculate_fantasy_points: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Invalid JSON in player_stats: {e!s}",
        }, indent=2)
    except ValueError as e:
        logger.error(f"Failed to get league scoring settings: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Could not fetch league scoring settings: {e!s}",
        }, indent=2)
    except Exception as e:
        logger.error(f"Error calculating fantasy points: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return json.dumps({
            "status": "error",
            "error": str(e),
        }, indent=2)
