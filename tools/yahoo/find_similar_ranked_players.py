"""Tool to find players with similar or worse rankings for trade comparison."""

import json

from langchain.tools import tool

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
        "owner_team_key": None,
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
                player_info["owner_team_key"] = ownership.get("owner_team_key")
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


def _find_similar_ranked_players_impl(
    user_email: str,
    league_id: str,
    target_rank: int,
    position: str = "",
    rank_range: int = 20,
    only_rostered: bool = True,
    exclude_my_team_id: str = "",
) -> str:
    """Internal implementation for find_similar_ranked_players."""
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        league_key = yahoo_client.query.get_league_key()

        # Calculate the rank range
        min_rank = max(1, target_rank - rank_range)
        max_rank = target_rank + rank_range

        # We need to fetch players starting from the min_rank position
        # start parameter is 0-indexed, so subtract 1
        start = max(0, min_rank - 1)
        count = max_rank - min_rank + 1

        # Build the URL with filters
        filters = ["sort=AR", "sort_type=season", f"start={start}", f"count={count}"]

        if position:
            filters.append(f"position={position}")

        if only_rostered:
            filters.append("status=T")  # T = Taken/rostered players only

        filter_str = ";".join(filters)
        url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

        logger.info(f"Fetching players ranked {min_rank}-{max_rank} with URL: {url}")

        response = yahoo_client.query.get_response(url)
        raw_json = response.json()

        fantasy_content = raw_json.get("fantasy_content", {})
        league_data = fantasy_content.get("league", [])

        if not isinstance(league_data, list) or len(league_data) < 2:
            logger.warning("Unexpected league data structure in response")
            return json.dumps(
                {"players": [], "message": f"No players found in rank range {min_rank}-{max_rank}"}
            )

        players_container = league_data[1] if len(league_data) > 1 else {}
        players_dict = players_container.get("players", {})

        result = []
        if isinstance(players_dict, dict):
            for key, value in players_dict.items():
                if key == "count":
                    continue
                if isinstance(value, dict) and "player" in value:
                    player_data = value["player"]
                    # Calculate actual rank: start (0-indexed) + position in results + 1
                    rank = start + int(key) + 1
                    player_info = _extract_player_with_rank(player_data, rank)

                    # Skip players on the user's team if exclude_my_team_id is provided
                    if exclude_my_team_id and player_info.get("owner_team_key"):
                        # owner_team_key format is like "nhl.l.12345.t.1"
                        # extract the team ID (last number after .t.)
                        team_key = str(player_info["owner_team_key"])
                        if f".t.{exclude_my_team_id}" in team_key:
                            continue

                    result.append(player_info)

        # Sort by rank just to be sure
        result.sort(key=lambda x: x.get("rank", 999))

        # Group players by owner for easier trade target identification
        players_by_owner = {}
        for player in result:
            owner = player.get("owner_team_name") or "Free Agent"
            if owner not in players_by_owner:
                players_by_owner[owner] = []
            players_by_owner[owner].append(player)

        return json.dumps(
            {
                "players": result,
                "players_by_owner": players_by_owner,
                "count": len(result),
                "rank_range": {"min": min_rank, "max": max_rank, "target": target_rank},
                "filters": {
                    "position": position or "all",
                    "only_rostered": only_rostered,
                    "excluded_team_id": exclude_my_team_id or None,
                },
                "message": f"Found {len(result)} players ranked {min_rank}-{max_rank}",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching similar ranked players: {e}")
        return json.dumps({"error": str(e), "players": []})


# Expose for internal use by other Python code
find_similar_ranked_players_internal = _find_similar_ranked_players_impl


@tool
def find_similar_ranked_players(
    user_email: str,
    league_id: str,
    target_rank: int,
    position: str = "",
    rank_range: int = 20,
    only_rostered: bool = True,
    exclude_my_team_id: str = "",
) -> str:
    """
    Find players with similar or worse rankings for trade comparison.

    This tool finds players ranked around a target rank (or worse) to identify
    potential trade targets. Players with worse fantasy point production but
    better advanced stats (xGoals, Fenwick, TOI) may have higher upside potential.

    Args:
        user_email: User's email address (used to look up OAuth tokens in database)
        league_id: Yahoo league ID
        target_rank: The rank to search around
        position: Optional position filter (e.g., "C", "LW", "RW", "D", "G", "F")
        rank_range: How many ranks above and below to include (default 20)
        only_rostered: If True, only return players on teams (not free agents)
        exclude_my_team_id: Optional team ID to exclude from results (your team)

    Returns:
        JSON string with list of players in the rank range, sorted by rank.
    """
    return _find_similar_ranked_players_impl(
        user_email, league_id, target_rank, position, rank_range, only_rostered, exclude_my_team_id
    )
