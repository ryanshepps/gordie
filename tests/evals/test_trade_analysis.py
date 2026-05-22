"""Trade analysis workflow evals for fantasy hockey agent."""

import pytest
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

KNOWN_PLAYERS = (
    "fiala",
    "buchnevich",
    "cozens",
    "nelson",
    "teravainen",
    "boeser",
    "guentzel",
    "forsberg",
    "kaprizov",
    "draisaitl",
    "mcdavid",
    "meier",
)

STATS_KEYWORDS = ("points", "goals", "assists", "gp", "games")
ADVANCED_STATS_KEYWORDS = ("xgoal", "corsi", "fenwick", "toi", "ice time", "possession")

XGOALS_KEYWORDS = ("xgoal", "expected goal", "goals above expected", "gax")
POSSESSION_KEYWORDS = ("fenwick", "corsi", "possession", "shot share")
UNDERVALUE_KEYWORDS = (
    "undervalued",
    "regression",
    "unlucky",
    "due for",
    "below expected",
    "underperforming",
)


class TestTradeAnalysisWorkflow:
    @pytest.fixture
    def trade_analysis_input(self) -> str:
        return "I want to trade away Draisaitl, who should I target?"

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_response_includes_trade_targets_with_stats(
        self,
        mock_user_state,
        mock_yahoo_tools,
        trade_analysis_input,
    ):
        mock_user_state["messages"] = [HumanMessage(content=trade_analysis_input)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        player_mentions = sum(1 for p in KNOWN_PLAYERS if p in response_lower)
        assert player_mentions >= 2, (
            f"Expected 2+ player names in response, found {player_mentions}: {response_text[:500]}"
        )

        assert any(kw in response_lower for kw in STATS_KEYWORDS), (
            f"Expected stats keywords in response: {response_text[:500]}"
        )

        assert any(kw in response_lower for kw in ADVANCED_STATS_KEYWORDS), (
            f"Expected advanced stats keywords in response: {response_text[:500]}"
        )


class TestTradeTargetQuality:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_does_not_recommend_obviously_better_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        input_text = "Troy Terry hasn't been performing well, who should I trade for?"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "").lower()

        elite_players = [
            "connor mcdavid",
            "nathan mackinnon",
            "nikita kucherov",
            "leon draisaitl",
            "auston matthews",
            "david pastrnak",
        ]

        elite_recommendations = sum(1 for player in elite_players if player in response_text)

        assert elite_recommendations <= 1, (
            f"Should not recommend multiple elite players as trade targets for mid-tier player. "
            f"Found {elite_recommendations} elite players mentioned. Response: {response_text[:800]}..."
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_recommends_players_with_upside_indicators(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        input_text = "I want to trade away a struggling player, find me undervalued targets"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "").lower()

        upside_indicators = [
            "undervalued",
            "regression",
            "expected goal",
            "xgoal",
            "below expected",
            "unlucky",
            "due for",
            "fenwick",
            "possession",
            "ice time",
            "toi",
            "first line",
            "top line",
            "schedule",
        ]

        indicator_count = sum(1 for ind in upside_indicators if ind in response_text)

        assert indicator_count >= 3, (
            f"Response should mention at least 3 upside indicators. "
            f"Found {indicator_count}. Response: {response_text[:800]}..."
        )


class TestTradeAgentUndervaluedIntegration:
    @pytest.fixture
    def trade_for_input(self) -> str:
        return "I want to acquire a new center with good underlying stats"

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_response_quality_with_undervalued_analysis(
        self,
        mock_user_state,
        mock_yahoo_tools,
        trade_for_input,
    ):
        mock_user_state["messages"] = [HumanMessage(content=trade_for_input)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert any(kw in response_lower for kw in XGOALS_KEYWORDS), (
            f"Expected xGoals-related keywords in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in POSSESSION_KEYWORDS), (
            f"Expected possession-related keywords in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in UNDERVALUE_KEYWORDS), (
            f"Expected undervaluation-related keywords in response: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_prioritizes_high_undervalued_score_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        input_text = "Find me a player who is shooting below their expected goals rate"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "").lower()

        regression_terms = [
            "regression",
            "expected",
            "xgoal",
            "shooting",
            "unlucky",
            "below expected",
            "due for",
            "underperforming",
        ]

        mentions_regression = any(term in response_text for term in regression_terms)

        assert mentions_regression, (
            f"Response should discuss regression candidates. Response: {response_text[:500]}..."
        )
