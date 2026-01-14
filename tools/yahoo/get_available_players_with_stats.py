"""Consolidated tool to get available players with comprehensive stats in one call."""

import json
from concurrent.futures import ThreadPoolExecutor

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.player_comparison.get_comprehensive_player_stats import (
    get_comprehensive_player_stats_internal,
)

logger = get_logger(__name__)


def _extract_player_info(player_data: list[object]) -> dict[str, str | None]:
    """Extract player info from the raw Yahoo API player data structure."""
    player_info = {
        "name": "Unknown",
        "player_key": None,
        "player_id": None,
        "position": None,
        "team": None,
        "team_full": None,
        "status": "available",
        "injury_status": None,
        "percent_owned": None,
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
        elif "player_id" in attr_dict:
            player_info["player_id"] = attr_dict["player_id"]
        elif "display_position" in attr_dict:
            player_info["position"] = attr_dict["display_position"]
        elif "editorial_team_abbr" in attr_dict:
            player_info["team"] = attr_dict["editorial_team_abbr"]
        elif "editorial_team_full_name" in attr_dict:
            player_info["team_full"] = attr_dict["editorial_team_full_name"]
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


def _fetch_players_by_status(
    yahoo_client: AuthenticatedYahooClient,
    league_key: str,
    status: str,
    count: int,
    sort: str,
    sort_type: str,
) -> list[dict[str, str | None]]:
    """Fetch players with a specific availability status."""
    filters = [f"status={status}", f"count={count}", f"sort={sort}", f"sort_type={sort_type}"]
    filter_str = ";".join(filters)
    url = f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;{filter_str}"

    logger.info(f"Fetching {status} players with URL: {url}")

    response = yahoo_client.query.get_response(url)
    raw_json = response.json()

    fantasy_content = raw_json.get("fantasy_content", {})
    league_data = fantasy_content.get("league", [])

    if not isinstance(league_data, list) or len(league_data) < 2:
        return []

    players_container = league_data[1] if len(league_data) > 1 else {}
    players_dict = players_container.get("players", {})

    result = []
    if isinstance(players_dict, dict):
        for key, value in players_dict.items():
            if key == "count":
                continue
            if isinstance(value, dict) and "player" in value:
                player_data = value["player"]
                player_info = _extract_player_info(player_data)
                player_info["availability_type"] = status
                result.append(player_info)
    elif isinstance(players_dict, list):
        for entry in players_dict:
            if isinstance(entry, dict) and "player" in entry:
                player_data = entry["player"]
                player_info = _extract_player_info(player_data)
                player_info["availability_type"] = status
                result.append(player_info)

    return result


@tool
def get_available_players_with_stats(
    user_email: str,
    league_id: str,
    count_per_status: int = 15,
    enrich_top_n: int = 10,
    sort: str = "AR",
    sort_type: str = "lastweek",
    situation: str = "all",
) -> str:
    """
    Get available players (FA + Waivers) with comprehensive stats in ONE call.

    This consolidated tool fetches both free agents and waiver players, then
    enriches the top players with comprehensive stats including MoneyPuck
    advanced analytics, schedule info, linemate data, and undervalued scoring.

    Use this instead of calling get_available_players + get_comprehensive_player_stats
    separately. This is more efficient and provides everything needed for
    pickup recommendations.

    Args:
        user_email: User's email address for Yahoo authentication
        league_id: Yahoo league ID
        count_per_status: Number of players to fetch per status (FA and W). Default 15.
        enrich_top_n: Number of top players per status to enrich with full stats. Default 10.
        sort: Sort order - "AR" (actual rank) recommended for recent performance
        sort_type: Time period - "lastweek" recommended for streaming
        situation: MoneyPuck situation filter (all, 5on5, 5on4, 4on5)

    Returns:
        JSON with:
        - free_agents: List of FA players with stats
        - waiver_players: List of W players with stats
        - enriched_stats: Comprehensive stats for top players from both lists
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        league_key = yahoo_client.query.get_league_key()

        # Fetch FA and W players in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            fa_future = executor.submit(
                _fetch_players_by_status,
                yahoo_client,
                league_key,
                "FA",
                count_per_status,
                sort,
                sort_type,
            )
            w_future = executor.submit(
                _fetch_players_by_status,
                yahoo_client,
                league_key,
                "W",
                count_per_status,
                sort,
                sort_type,
            )

            fa_players = fa_future.result()
            w_players = w_future.result()

        logger.info(f"Fetched {len(fa_players)} FA and {len(w_players)} W players")

        # Select top N from each for enrichment
        fa_to_enrich = fa_players[:enrich_top_n]
        w_to_enrich = w_players[:enrich_top_n]

        # Collect all player names for stats enrichment
        all_names_to_enrich = [name for p in fa_to_enrich + w_to_enrich if isinstance(name := p.get("name"), str)]

        # Fetch comprehensive stats for all players in one batch
        enriched_stats = {}
        if all_names_to_enrich:
            logger.info(f"Enriching stats for {len(all_names_to_enrich)} players")
            try:
                stats_response = get_comprehensive_player_stats_internal(
                    player_names=all_names_to_enrich,
                    user_email=user_email,
                    league_id=league_id,
                    situation=situation,
                )
                enriched_stats = json.loads(stats_response)
            except Exception as e:
                logger.error(f"Failed to enrich player stats: {e}")
                enriched_stats = {"error": str(e)}

        # Merge enriched stats back into player lists
        def merge_stats(players, stats):
            """Merge comprehensive stats into player info."""
            for player in players:
                name = player.get("name")
                if name and name in stats:
                    player_stats = stats[name]
                    if player_stats.get("status") == "success":
                        player["comprehensive_stats"] = player_stats
            return players

        fa_players = merge_stats(fa_players, enriched_stats)
        w_players = merge_stats(w_players, enriched_stats)

        return json.dumps(
            {
                "free_agents": fa_players,
                "waiver_players": w_players,
                "fa_count": len(fa_players),
                "waiver_count": len(w_players),
                "enriched_count": len([p for p in fa_players + w_players if "comprehensive_stats" in p]),
                "filters": {
                    "sort": sort,
                    "sort_type": sort_type,
                    "count_per_status": count_per_status,
                    "enrich_top_n": enrich_top_n,
                },
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error in get_available_players_with_stats: {e}")
        return json.dumps({"error": str(e), "free_agents": [], "waiver_players": []})
