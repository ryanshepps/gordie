from collections.abc import Sequence

from langchain.agents.middleware import wrap_model_call

from agent.context_types import Sport

SPORT_TOOLS: dict[Sport, set[str]] = {
    "nhl": {
        "query_hockey_stats_db",
        "calculate_undervalued_score",
        "get_team_schedule",
        "fuzzy_resolve_nhl_api_player_ids",
    },
    "mlb": {
        "query_mlb_stats_db",
        "calculate_mlb_undervalued_score",
        "get_mlb_team_schedule",
        "fuzzy_resolve_mlb_player_ids",
    },
}

ALL_SPORT_TOOLS = {name for names in SPORT_TOOLS.values() for name in names}


def filter_tools_by_sport[T](tools: Sequence[T], sport: Sport | None) -> list[T]:
    if sport is None:
        return list(tools)

    allowed = SPORT_TOOLS.get(sport, set())
    return [
        t for t in tools
        if getattr(t, "name", "") not in ALL_SPORT_TOOLS
        or getattr(t, "name", "") in allowed
    ]


@wrap_model_call
def sport_tool_filter(request, handler):
    sport = request.state.get("sport")
    filtered = filter_tools_by_sport(request.tools, sport)
    return handler(request.override(tools=filtered))
