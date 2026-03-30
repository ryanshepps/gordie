from types import SimpleNamespace

from middleware.sport_tool_filter import ALL_SPORT_TOOLS, filter_tools_by_sport


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


ALL_TOOLS = [
    _tool("query_hockey_stats_db"),
    _tool("calculate_undervalued_score"),
    _tool("query_mlb_stats_db"),
    _tool("calculate_mlb_undervalued_score"),
    _tool("onboard_user_team"),
    _tool("yahoo_roster"),
]


def _names(tools: list[SimpleNamespace]) -> list[str]:
    return [t.name for t in tools]


class TestFilterToolsBySport:
    def test_hockey_excludes_mlb_tools(self):
        result = _names(filter_tools_by_sport(ALL_TOOLS, "nhl"))

        assert "query_hockey_stats_db" in result
        assert "calculate_undervalued_score" in result
        assert "query_mlb_stats_db" not in result
        assert "calculate_mlb_undervalued_score" not in result

    def test_baseball_excludes_hockey_tools(self):
        result = _names(filter_tools_by_sport(ALL_TOOLS, "mlb"))

        assert "query_mlb_stats_db" in result
        assert "calculate_mlb_undervalued_score" in result
        assert "query_hockey_stats_db" not in result
        assert "calculate_undervalued_score" not in result

    def test_non_sport_tools_always_included(self):
        result = _names(filter_tools_by_sport(ALL_TOOLS, "nhl"))

        assert "onboard_user_team" in result
        assert "yahoo_roster" in result

    def test_no_sport_passes_all_tools(self):
        result = filter_tools_by_sport(ALL_TOOLS, None)

        assert len(result) == len(ALL_TOOLS)

    def test_unknown_sport_excludes_all_sport_tools(self):
        result = _names(filter_tools_by_sport(ALL_TOOLS, "nba"))

        sport_tools_in_result = [t for t in result if t in ALL_SPORT_TOOLS]
        assert sport_tools_in_result == []
        assert "onboard_user_team" in result
        assert "yahoo_roster" in result
