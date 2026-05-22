"""Yahoo Fantasy scoring, matchup, and standings data tool."""

import json
from typing import Annotated

from langchain.tools import InjectedState, tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.user_context import get_user_id
from tools.yahoo_stats.serializer import (
    serialize_generic,
    serialize_matchup,
    serialize_team,
)

logger = get_logger(__name__)

VALID_METHODS = {
    "get_league_scoreboard_by_week",
    "get_league_matchups_by_week",
    "get_team_stats",
    "get_team_stats_by_week",
    "get_team_matchups",
    "get_league_standings",
    "get_team_standings",
}


@tool
def yahoo_scoring(
    league_id: str,
    method: str,
    params_json: str = "{}",
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """Query Yahoo Fantasy scoring, matchup, and standings data.

    Available methods:

    - get_league_scoreboard_by_week: All matchup scores for a given week.
      Params: {"week": int}
      Returns: List of matchups with team names, scores, and winner.

    - get_league_matchups_by_week: Matchups with full stat breakdowns for a week.
      Params: {"week": int}
      Returns: Detailed matchup data including per-category stats.

    - get_team_stats: Season-long totals for a specific team.
      Params: {"team_id": str}
      Returns: Aggregated season stats for the team.

    - get_team_stats_by_week: Weekly team totals and projections.
      Params: {"team_id": str, "week": int}
      Returns: Team stats for the specified week.

    - get_team_matchups: Full season schedule with results for a team.
      Params: {"team_id": str}
      Returns: All matchups for the season with outcomes.

    - get_league_standings: W/L/T, points for/against, rank for all teams.
      Params: {} (none required)
      Returns: All teams with standings data.

    - get_team_standings: Single team's standing details.
      Params: {"team_id": str}
      Returns: Standings for the specified team.

    Args:
        league_id: Yahoo league ID.
        method: One of the available methods listed above.
        params_json: JSON string of method parameters (default: "{}").

    Returns:
        JSON string with the requested data.
    """
    if method not in VALID_METHODS:
        return json.dumps(
            {"error": f"Invalid method '{method}'. Valid methods: {sorted(VALID_METHODS)}"}
        )

    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_id=get_user_id(state))
    params: dict[str, str | int | float] = json.loads(params_json)

    try:
        query = yahoo_client.query

        if method == "get_league_scoreboard_by_week":
            raw = query.get_league_scoreboard_by_week(int(params["week"]))
            scoreboard_matchups = getattr(raw, "matchups", None)
            if isinstance(scoreboard_matchups, list):
                matchups = scoreboard_matchups
            elif isinstance(raw, list):
                matchups = raw
            else:
                matchups = [raw]
            data = [serialize_matchup(m) for m in matchups]
            return json.dumps({"matchups": data, "week": params["week"]}, default=str)

        if method == "get_league_matchups_by_week":
            raw = query.get_league_matchups_by_week(int(params["week"]))
            matchups = raw if isinstance(raw, list) else [raw]
            data = [serialize_matchup(m) for m in matchups]
            return json.dumps({"matchups": data, "week": params["week"]}, default=str)

        if method == "get_team_stats":
            raw = query.get_team_stats(str(params["team_id"]))
            return json.dumps({"team_stats": serialize_generic(raw)}, default=str)

        if method == "get_team_stats_by_week":
            raw = query.get_team_stats_by_week(str(params["team_id"]), int(params["week"]))
            return json.dumps({"team_stats": serialize_generic(raw)}, default=str)

        if method == "get_team_matchups":
            raw = query.get_team_matchups(str(params["team_id"]))
            matchups = raw if isinstance(raw, list) else [raw]
            data = [serialize_matchup(m) for m in matchups]
            return json.dumps({"matchups": data, "team_id": params["team_id"]}, default=str)

        if method == "get_league_standings":
            raw = query.get_league_standings()
            teams = raw if isinstance(raw, list) else [raw]
            data = [serialize_team(t) for t in teams]
            return json.dumps({"standings": data}, default=str)

        if method == "get_team_standings":
            raw = query.get_team_standings(str(params["team_id"]))
            return json.dumps({"standings": serialize_team(raw)}, default=str)

        return json.dumps({"error": f"Unhandled method: {method}"})

    except Exception as e:
        logger.error(f"yahoo_scoring error ({method}): {e}")
        return json.dumps({"error": str(e), "method": method})
