"""Yahoo Fantasy league context, draft, and transaction data tool."""

import json

from langchain.tools import tool

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from module.logger import get_logger
from tools.yahoo_stats.serializer import (
    serialize_draft_pick,
    serialize_generic,
    serialize_league_info,
    serialize_team,
    serialize_transaction,
)

logger = get_logger(__name__)

VALID_METHODS = {
    "get_league_draft_results",
    "get_team_draft_results",
    "get_player_draft_analysis",
    "get_league_transactions",
    "get_league_info",
    "get_league_settings",
    "get_league_teams",
}


@tool
def yahoo_league(
    user_email: str,
    league_id: str,
    method: str,
    params_json: str = "{}",
) -> str:
    """Query Yahoo Fantasy league context, draft results, transactions, and settings.

    Available methods:

    - get_league_draft_results: All draft picks for the league.
      Params: {} (none required)
      Returns: List of picks with round, pick number, team, and player.

    - get_team_draft_results: Draft picks for a specific team.
      Params: {"team_id": str}
      Returns: List of that team's draft picks.

    - get_player_draft_analysis: Average draft position (ADP) data for a player.
      Params: {"player_key": str} (e.g. "nhl.p.5017")
      Returns: ADP and draft analysis for the player.

    - get_league_transactions: All trades, adds, and drops in the league.
      Params: {} (none required)
      Returns: List of transactions with type, players involved, and timestamps.

    - get_league_info: Current week, season start/end dates, and league metadata.
      Params: {} (none required)
      Returns: League info including current_week, start_date, end_date.

    - get_league_settings: Scoring categories, roster positions, and league rules.
      Params: {} (none required)
      Returns: Full league settings including stat categories and their weights.

    - get_league_teams: All teams with IDs, names, managers, and standings.
      Params: {} (none required)
      Returns: List of all teams in the league.

    Args:
        user_email: User's email for OAuth token lookup.
        league_id: Yahoo league ID.
        method: One of the available methods listed above.
        params_json: JSON string of method parameters (default: "{}").

    Returns:
        JSON string with the requested league data.
    """
    if method not in VALID_METHODS:
        return json.dumps(
            {"error": f"Invalid method '{method}'. Valid methods: {sorted(VALID_METHODS)}"}
        )

    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)
    params: dict[str, str | int | float] = json.loads(params_json)

    try:
        query = yahoo_client.query

        if method == "get_league_draft_results":
            raw = query.get_league_draft_results()
            picks = raw if isinstance(raw, list) else [raw]
            data = [serialize_draft_pick(p) for p in picks]
            return json.dumps({"draft_results": data}, default=str)

        if method == "get_team_draft_results":
            raw = query.get_team_draft_results(str(params["team_id"]))
            picks = raw if isinstance(raw, list) else [raw]
            data = [serialize_draft_pick(p) for p in picks]
            return json.dumps({"draft_results": data, "team_id": params["team_id"]}, default=str)

        if method == "get_player_draft_analysis":
            raw = query.get_player_draft_analysis(str(params["player_key"]))
            return json.dumps({"draft_analysis": serialize_generic(raw)}, default=str)

        if method == "get_league_transactions":
            raw = query.get_league_transactions()
            transactions = raw if isinstance(raw, list) else [raw]
            data = [serialize_transaction(t) for t in transactions]
            return json.dumps({"transactions": data}, default=str)

        if method == "get_league_info":
            raw = query.get_league_info()
            return json.dumps({"league_info": serialize_league_info(raw)}, default=str)

        if method == "get_league_settings":
            raw = query.get_league_settings()
            return json.dumps({"league_settings": serialize_generic(raw)}, default=str)

        if method == "get_league_teams":
            raw = query.get_league_teams()
            teams = raw if isinstance(raw, list) else [raw]
            data = [serialize_team(t) for t in teams]
            return json.dumps({"teams": data}, default=str)

        return json.dumps({"error": f"Unhandled method: {method}"})

    except Exception as e:
        logger.error(f"yahoo_league error ({method}): {e}")
        return json.dumps({"error": str(e), "method": method})
