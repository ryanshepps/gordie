"""Tool to resolve player names to NHL API player IDs."""

import json
from typing import Any

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)


class ResolvePlayerNamesInput(BaseModel):
    """Input schema for resolve_player_names tool."""

    player_names: list[str] = Field(
        description="List of player names to resolve (e.g., ['McDavid', 'Draisaitl'])"
    )


@tool(args_schema=ResolvePlayerNamesInput)
def resolve_player_names(player_names: list[str]) -> str:
    """
    Resolve player names to NHL API player IDs using local database and NHL search API.

    This tool uses a two-tier approach:
    1. First searches the local nhl_player_stats table with fuzzy matching
    2. Falls back to NHL search API if not found locally

    Args:
        player_names: List of player names to search for (e.g., ['McDavid', 'Draisaitl'])

    Returns:
        JSON string containing resolved player information with player_id, full_name, and match details
    """
    from data.nhl_player_stats_repository import NHLPlayerStatsRepository

    repo = NHLPlayerStatsRepository()
    results: dict[str, Any] = {}

    try:
        for player_name in player_names:
            try:
                logger.info(f"Searching for player: {player_name}")

                # Step 1: Search local database with fuzzy matching
                # Use ILIKE for case-insensitive matching on last name or full name
                search_term = f"%{player_name}%"
                query = """
                    SELECT DISTINCT
                        nhl_api_player_id,
                        full_name,
                        first_name,
                        last_name,
                        COUNT(*) as games_in_db
                    FROM nhl_player_stats
                    WHERE full_name ILIKE ? OR last_name ILIKE ?
                    GROUP BY nhl_api_player_id, full_name, first_name, last_name
                    ORDER BY games_in_db DESC
                    LIMIT 5
                """

                local_matches = repo.conn.execute(query, [search_term, search_term]).fetchall()

                if local_matches:
                    # Found matches in local database
                    if len(local_matches) == 1:
                        # Exact match found
                        match = local_matches[0]
                        results[player_name] = {
                            "status": "success",
                            "source": "local_database",
                            "player_id": match[0],
                            "full_name": match[1],
                            "first_name": match[2],
                            "last_name": match[3],
                            "games_in_db": match[4]
                        }
                        logger.info(f"Found exact match for '{player_name}': {match[1]} (ID: {match[0]})")
                    else:
                        # Multiple matches - return all for disambiguation
                        results[player_name] = {
                            "status": "multiple_matches",
                            "source": "local_database",
                            "matches": [
                                {
                                    "player_id": m[0],
                                    "full_name": m[1],
                                    "first_name": m[2],
                                    "last_name": m[3],
                                    "games_in_db": m[4]
                                }
                                for m in local_matches
                            ],
                            "message": f"Found {len(local_matches)} possible matches. Please be more specific."
                        }
                        logger.info(f"Found {len(local_matches)} matches for '{player_name}'")
                else:
                    # Step 2: Fallback to NHL search API
                    logger.info(f"No local match for '{player_name}', trying NHL API")

                    try:
                        api_url = f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=5&q={player_name}"
                        response = requests.get(api_url, timeout=5)
                        response.raise_for_status()

                        api_results = response.json()

                        if api_results and len(api_results) > 0:
                            if len(api_results) == 1:
                                # Single match from API
                                api_player = api_results[0]
                                results[player_name] = {
                                    "status": "success",
                                    "source": "nhl_api",
                                    "player_id": int(api_player.get("playerId", 0)),
                                    "full_name": api_player.get("name", ""),
                                    "team_abbrev": api_player.get("teamAbbrev"),
                                    "position": api_player.get("positionCode"),
                                    "active": api_player.get("active", False),
                                    "message": "Player found via NHL API. Stats may not be in local database yet."
                                }
                                logger.info(f"Found NHL API match for '{player_name}': {api_player.get('name')}")
                            else:
                                # Multiple API matches
                                results[player_name] = {
                                    "status": "multiple_matches",
                                    "source": "nhl_api",
                                    "matches": [
                                        {
                                            "player_id": int(p.get("playerId", 0)),
                                            "full_name": p.get("name", ""),
                                            "team_abbrev": p.get("teamAbbrev"),
                                            "position": p.get("positionCode"),
                                            "active": p.get("active", False)
                                        }
                                        for p in api_results
                                    ],
                                    "message": f"Found {len(api_results)} possible matches from NHL API. Please be more specific."
                                }
                                logger.info(f"Found {len(api_results)} NHL API matches for '{player_name}'")
                        else:
                            results[player_name] = {
                                "status": "not_found",
                                "message": f"No player found matching '{player_name}' in database or NHL API"
                            }
                            logger.warning(f"No matches found for '{player_name}'")

                    except requests.RequestException as api_error:
                        logger.error(f"NHL API error for '{player_name}': {api_error}")
                        results[player_name] = {
                            "status": "error",
                            "message": f"Could not search NHL API: {api_error!s}"
                        }

            except Exception as e:
                logger.error(f"Error resolving '{player_name}': {e}")
                results[player_name] = {
                    "status": "error",
                    "error": str(e)
                }
    finally:
        repo.close()

    return json.dumps(results, indent=2)
