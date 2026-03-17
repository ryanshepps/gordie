"""Yahoo Fantasy individual player lookup and league-wide player browsing tool."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.yahoo_stats.serializer import serialize_generic, serialize_player

logger = get_logger(__name__)

VALID_METHODS = {
    "get_player_stats_for_season",
    "get_player_stats_by_week",
    "get_player_stats_by_date",
    "get_league_players",
}


@tool
def yahoo_player(
    user_email: str,
    league_id: str,
    method: str,
    params_json: str = "{}",
) -> str:
    """Query Yahoo Fantasy for individual player stats or browse league players.

    Available methods:

    - get_player_stats_for_season: Any player's full season stats.
      Params: {"player_key": str} (e.g. "nhl.p.5017")
      Returns: Player info with season stats and fantasy points.

    - get_player_stats_by_week: Any player's stats for a specific week.
      Params: {"player_key": str, "week": int}
      Returns: Player info with stats for that week.

    - get_player_stats_by_date: Any player's stats for a specific date.
      Params: {"player_key": str, "date": str} (date format: "YYYY-MM-DD")
      Returns: Player info with stats for that date.

    - get_league_players: Browse all players in the league (paginated).
      Params: {"player_count_limit": int, "player_count_start": int}
      Returns: List of players starting from the offset, up to the limit.

    Args:
        user_email: User's email for OAuth token lookup.
        league_id: Yahoo league ID.
        method: One of the available methods listed above.
        params_json: JSON string of method parameters (default: "{}").

    Returns:
        JSON string with player data.
    """
    if method not in VALID_METHODS:
        return json.dumps({
            "error": f"Invalid method '{method}'. Valid methods: {sorted(VALID_METHODS)}"
        })

    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)
    params: dict[str, str | int | float] = json.loads(params_json)

    try:
        query = yahoo_client.query

        if method == "get_player_stats_for_season":
            raw = query.get_player_stats_for_season(str(params["player_key"]))
            return json.dumps({"player": serialize_player(raw)}, default=str)

        if method == "get_player_stats_by_week":
            raw = query.get_player_stats_by_week(str(params["player_key"]), int(params["week"]))
            return json.dumps({"player": serialize_player(raw)}, default=str)

        if method == "get_player_stats_by_date":
            raw = query.get_player_stats_by_date(str(params["player_key"]), str(params["date"]))
            return json.dumps({"player": serialize_player(raw)}, default=str)

        if method == "get_league_players":
            limit = int(params.get("player_count_limit", 25))
            start = int(params.get("player_count_start", 0))
            raw = query.get_league_players(
                player_count_limit=limit,
                player_count_start=start,
            )
            players = raw if isinstance(raw, list) else [raw]
            data = [serialize_generic(p) for p in players]
            return json.dumps({"players": data, "count": len(data)}, default=str)

        return json.dumps({"error": f"Unhandled method: {method}"})

    except Exception as e:
        logger.error(f"yahoo_player error ({method}): {e}")
        return json.dumps({"error": str(e), "method": method})
