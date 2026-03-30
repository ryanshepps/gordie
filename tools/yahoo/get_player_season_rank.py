"""Tool to get a player's current season rank in a fantasy league."""

import json
from urllib.parse import quote

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger

logger = get_logger(__name__)


def _extract_player_with_rank(player_data: list[object], rank: int) -> dict[str, str | int | None]:
    """Extract player info including rank from the raw Yahoo API player data structure.

    The Yahoo API returns player data as a list of dicts, where each dict
    contains a single attribute. This function flattens that structure.
    """
    player_info = {
        "name": "Unknown",
        "player_key": None,
        "player_id": None,
        "position": None,
        "team": None,
        "team_full": None,
        "rank": rank,
        "ownership_type": None,
        "owner_team_name": None,
        "status": None,
        "injury_status": None,
        "percent_owned": None,
    }

    if not player_data or not isinstance(player_data, list):
        return player_info

    # First element is a list of dicts with player attributes
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
        elif "player_id" in attr_dict:
            player_info["player_id"] = attr_dict["player_id"]
        elif "display_position" in attr_dict:
            player_info["position"] = attr_dict["display_position"]
        elif "editorial_team_abbr" in attr_dict:
            player_info["team"] = attr_dict["editorial_team_abbr"]
        elif "editorial_team_full_name" in attr_dict:
            player_info["team_full"] = attr_dict["editorial_team_full_name"]
        elif "ownership" in attr_dict:
            ownership = attr_dict["ownership"]
            if isinstance(ownership, dict):
                player_info["ownership_type"] = ownership.get("ownership_type")
                player_info["owner_team_name"] = ownership.get("owner_team_name")
        elif "status" in attr_dict:
            player_info["status"] = attr_dict["status"]
        elif "status_full" in attr_dict:
            player_info["injury_status"] = attr_dict["status_full"]
        elif "percent_owned" in attr_dict:
            pct_data = attr_dict["percent_owned"]
            if isinstance(pct_data, dict):
                player_info["percent_owned"] = pct_data.get("value")
            else:
                player_info["percent_owned"] = pct_data

    return player_info


def get_player_season_rank(
    user_email: str,
    league_id: str,
    player_name: str,
) -> str:
    """
    Get a player's current season rank in a fantasy league.

    This tool searches for a player by name and returns their current season
    ranking based on fantasy points (AR = Actual Rank). The rank represents
    where the player stands among all players in the league based on season
    fantasy point production.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        player_name: The name of the player to search for (e.g., "Connor McDavid", "McDavid")

    Returns:
        JSON string with the player's rank and information, or an error if not found.
        The rank field indicates the player's current season position (1 = best).
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        league_key = yahoo_client.query.get_league_key()

        # Search for the player by name, sorted by actual rank (fantasy points)
        # We fetch more players to ensure we can find the player's true rank
        encoded_name = quote(player_name, safe="")
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;search={encoded_name};sort=AR;count=25"

        logger.info(f"Searching for player rank: {player_name}")

        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        if not isinstance(league_data, list) or len(league_data) < 2:
            logger.warning("Unexpected league data structure in response")
            return json.dumps({"error": f"Player '{player_name}' not found", "player": None})

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        # If player was found in search, we need to get their actual rank
        # by searching through the full ranked list
        search_results = []
        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    # Rank starts from 1, key is 0-indexed
                    player_info = _extract_player_with_rank(player_data, int(key) + 1)
                    search_results.append(player_info)

        if not search_results:
            return json.dumps({"error": f"Player '{player_name}' not found", "player": None})

        # The first result should be the best match
        best_match = search_results[0]

        # Now we need to find the player's actual rank in the full league standings
        # We do this by getting players sorted by AR and finding position
        # We'll iterate through pages of 25 players until we find them or reach a limit
        actual_rank = None
        max_players_to_check = 500  # Limit to avoid excessive API calls

        for start in range(0, max_players_to_check, 25):
            url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;sort=AR;sort_type=season;start={start};count=25"

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

                        # Check if this is our player
                        attrs_list = player_data[0] if player_data else []
                        if isinstance(attrs_list, list):
                            for attr_dict in attrs_list:
                                if (
                                    isinstance(attr_dict, dict)
                                    and "player_key" in attr_dict
                                    and attr_dict["player_key"] == best_match["player_key"]
                                ):
                                    actual_rank = rank
                                    break
                    if actual_rank:
                        break
            if actual_rank:
                break

        if actual_rank:
            best_match["rank"] = actual_rank

        return json.dumps(
            {
                "player": best_match,
                "message": f"Found {best_match['name']} ranked #{best_match['rank']} in the league",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching player rank: {e}")
        return json.dumps({"error": str(e), "player": None})
