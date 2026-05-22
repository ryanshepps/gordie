"""Tool to get Yahoo Fantasy league-specific information for players."""

import json
from typing import Annotated, Any
from urllib.parse import quote

from langchain.tools import InjectedState, tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.user_context import get_user_id

logger = get_logger(__name__)


def _extract_player_yahoo_info(player_data: list[object], rank: int) -> dict[str, str | int | None]:
    """Extract Yahoo-specific info from raw API player data structure."""
    player_info: dict[str, str | int | None] = {
        "name": "Unknown",
        "player_key": None,
        "position": None,
        "team": None,
        "yahoo_rank": rank,
        "percent_owned": None,
        "ownership_type": None,
        "owner_team_name": None,
        "injury_status": None,
    }

    if not player_data or not isinstance(player_data, list):
        return player_info

    attrs_list = player_data[0] if player_data else []
    if not isinstance(attrs_list, list):
        return player_info

    for attr_dict in attrs_list:
        if not isinstance(attr_dict, dict):
            continue

        if "name" in attr_dict:
            name_data = attr_dict["name"]
            if isinstance(name_data, dict):
                player_info["name"] = name_data.get("full", "Unknown")
            else:
                player_info["name"] = str(name_data)
        elif "player_key" in attr_dict:
            player_info["player_key"] = attr_dict["player_key"]
        elif "display_position" in attr_dict:
            player_info["position"] = attr_dict["display_position"]
        elif "editorial_team_abbr" in attr_dict:
            player_info["team"] = attr_dict["editorial_team_abbr"]
        elif "ownership" in attr_dict:
            ownership = attr_dict["ownership"]
            if isinstance(ownership, dict):
                player_info["ownership_type"] = ownership.get("ownership_type")
                player_info["owner_team_name"] = ownership.get("owner_team_name")
        elif "status_full" in attr_dict:
            player_info["injury_status"] = attr_dict["status_full"]
        elif "percent_owned" in attr_dict:
            pct_data = attr_dict["percent_owned"]
            if isinstance(pct_data, dict):
                player_info["percent_owned"] = pct_data.get("value")
            else:
                player_info["percent_owned"] = str(pct_data) if pct_data else None

    return player_info


def _find_player_rank(
    yahoo_client: AuthenticatedYahooClient,
    league_key: str,
    player_key: str,
    max_players: int = 500,
) -> int | None:
    """Find a player's actual rank by searching through league standings."""
    for start in range(0, max_players, 25):
        url = (
            f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;"
            f"sort=AR;sort_type=season;start={start};count=25"
        )

        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        if not isinstance(league_data, list) or len(league_data) < 2:
            break

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        if not players_dict or (
            isinstance(players_dict, dict) and players_dict.get("count", 0) == 0
        ):
            break

        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    rank = start + int(key) + 1

                    attrs_list = player_data[0] if player_data else []
                    if isinstance(attrs_list, list):
                        for attr_dict in attrs_list:
                            if (
                                isinstance(attr_dict, dict)
                                and "player_key" in attr_dict
                                and attr_dict["player_key"] == player_key
                            ):
                                return rank

    return None


@tool
def get_player_yahoo_info(
    league_id: str,
    player_names: list[str],
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """
    Get Yahoo Fantasy league-specific information for players.

    This tool looks up fantasy-specific data that varies by league.

    Args:
        league_id: Yahoo league ID
        player_names: List of player names to look up

    Returns:
        JSON with per-player Yahoo info:
        - yahoo_rank: Season ranking by fantasy points (1 = best)
        - percent_owned: Ownership percentage across Yahoo leagues
        - ownership_type: "freeagents", "waivers", or "team"
        - owner_team_name: Name of fantasy team that owns player (if rostered)
        - injury_status: Current injury designation (if any)

    Note:
        yahoo_rank is specific to this league's scoring settings.
        A player ranked #50 in one league may be #100 in another.
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_id=get_user_id(state))

    try:
        league_key = yahoo_client.query.get_league_key()
        result: dict[str, dict[str, Any]] = {}

        for player_name in player_names:
            # Search for player by name
            encoded_name = quote(player_name, safe="")
            url = (
                f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;"
                f"search={encoded_name};sort=AR;count=5"
            )

            logger.info(f"Looking up Yahoo info for: {player_name}")

            response = yahoo_client.query.get_response(url)
            raw_json = response.json()

            fantasy_content = raw_json.get("fantasy_content", {})
            league_data = fantasy_content.get("league", [])

            if not isinstance(league_data, list) or len(league_data) < 2:
                result[player_name] = {
                    "status": "error",
                    "message": f"Player '{player_name}' not found",
                }
                continue

            players_container = league_data[1] if len(league_data) > 1 else {}
            players_dict = players_container.get("players", {})

            # Get first matching player
            best_match = None
            if isinstance(players_dict, dict):
                for key, value in players_dict.items():
                    if key == "count":
                        continue
                    if isinstance(value, dict) and "player" in value:
                        player_data = value["player"]
                        best_match = _extract_player_yahoo_info(player_data, int(key) + 1)
                        break

            if not best_match:
                result[player_name] = {
                    "status": "error",
                    "message": f"Player '{player_name}' not found",
                }
                continue

            # Find actual rank in league standings
            player_key = best_match.get("player_key")
            if player_key and isinstance(player_key, str):
                actual_rank = _find_player_rank(yahoo_client, league_key, player_key)
                if actual_rank:
                    best_match["yahoo_rank"] = actual_rank

            result[player_name] = {
                "status": "success",
                **best_match,
            }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching Yahoo info: {e}")
        return json.dumps({"error": str(e)})
