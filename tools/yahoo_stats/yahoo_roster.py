"""Yahoo Fantasy roster and per-player stat data tool."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.yahoo_stats.serializer import serialize_player

logger = get_logger(__name__)

VALID_METHODS = {
    "get_team_roster_player_stats",
    "get_team_roster_player_stats_by_week",
    "get_team_roster_player_info_by_week",
    "get_team_roster_player_info_by_date",
}


@tool
def yahoo_roster(
    user_email: str,
    league_id: str,
    method: str,
    params_json: str = "{}",
) -> str:
    """Query Yahoo Fantasy roster and per-player stat data by team.

    Available methods:

    - get_team_roster_player_stats: Season stats for each player on a team's roster.
      Params: {"team_id": str}
      Returns: List of players with season stats and fantasy points.

    - get_team_roster_player_stats_by_week: Weekly stats for each player on a roster.
      Params: {"team_id": str, "week": int}
      Returns: List of players with stats for the specified week.

    - get_team_roster_player_info_by_week: Full player info for a roster in a given week.
      Params: {"team_id": str, "week": int}
      Returns: Detailed player info including eligibility and ownership.

    - get_team_roster_player_info_by_date: Daily roster snapshot (NHL daily leagues only).
      Params: {"team_id": str, "date": str} (date format: "YYYY-MM-DD")
      Returns: Roster snapshot for the specified date.

    Args:
        user_email: User's email for OAuth token lookup.
        league_id: Yahoo league ID.
        method: One of the available methods listed above.
        params_json: JSON string of method parameters (default: "{}").

    Returns:
        JSON string with roster/player data.
    """
    if method not in VALID_METHODS:
        return json.dumps({
            "error": f"Invalid method '{method}'. Valid methods: {sorted(VALID_METHODS)}"
        })

    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)
    params: dict[str, str | int | float] = json.loads(params_json)

    try:
        query = yahoo_client.query

        if method == "get_team_roster_player_stats":
            raw = query.get_team_roster_player_stats(str(params["team_id"]))
            players = raw if isinstance(raw, list) else [raw]
            data = [serialize_player(p) for p in players]
            return json.dumps({"players": data, "count": len(data)}, default=str)

        if method == "get_team_roster_player_stats_by_week":
            raw = query.get_team_roster_player_stats_by_week(
                str(params["team_id"]), int(params["week"])
            )
            players = raw if isinstance(raw, list) else [raw]
            data = [serialize_player(p) for p in players]
            return json.dumps({"players": data, "week": params["week"]}, default=str)

        if method == "get_team_roster_player_info_by_week":
            raw = query.get_team_roster_player_info_by_week(
                str(params["team_id"]), int(params["week"])
            )
            players = raw if isinstance(raw, list) else [raw]
            data = [serialize_player(p) for p in players]
            return json.dumps({"players": data, "week": params["week"]}, default=str)

        if method == "get_team_roster_player_info_by_date":
            raw = query.get_team_roster_player_info_by_date(
                str(params["team_id"]), str(params["date"])
            )
            players = raw if isinstance(raw, list) else [raw]
            data = [serialize_player(p) for p in players]
            return json.dumps({"players": data, "date": params["date"]}, default=str)

        return json.dumps({"error": f"Unhandled method: {method}"})

    except Exception as e:
        logger.error(f"yahoo_roster error ({method}): {e}")
        return json.dumps({"error": str(e), "method": method})
