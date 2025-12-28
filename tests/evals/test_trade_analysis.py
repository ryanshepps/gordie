"""Trade analysis workflow evals for fantasy hockey agent."""

from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


class TestTradeAnalysisWorkflow:
    """
    Test: "I want to trade away Draisaitl, who should I target?"

    Expected behavior:
    - Response includes 3+ trade targets with stats
    - Each target has specific stats cited (including advanced stats)
    - Reasoning is provided for recommendations
    """

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
        """Verify response includes 3+ trade targets with stats including advanced metrics."""
        mock_user_state["messages"] = [HumanMessage(content=trade_analysis_input)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        response_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey trade analysis response meets these criteria:
            1. Contains at least 3 trade target recommendations
            2. Each target includes specific stats (points, goals, assists, or advanced stats like xGoals, Corsi, Fenwick)
            3. Provides reasoning for why each target is a good match
            4. Mentions advanced analytics (xGoals, Corsi, Fenwick, TOI, possession, ice time) for at least some players

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 if all criteria met, 0.5 if partially met, 0.0 if not met.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = response_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] == 1.0, (
            f"Response quality issue: {eval_dict.get('comment', eval_dict)}"
        )


class TestTradeTargetQuality:
    """
    Tests that the trade agent recommends UNDERVALUED players, not obviously better ones.

    The agent should NOT recommend players who are:
    - Ranked significantly higher than the subject player
    - Already elite performers (top 10 rank)
    - Obviously better by all metrics

    Instead, it should recommend players who:
    - Have worse rank but better underlying stats (xGoals, Fenwick%, TOI)
    - Are on better lines (1st/2nd line vs 3rd/4th)
    - Have favorable schedules
    - Show signs of positive regression (negative goals above expected)
    """

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_does_not_recommend_obviously_better_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        """
        Trade agent should not recommend elite players (rank 1-10) as trade targets
        for a mid-tier player. Elite players are not realistic trade targets.

        Scenario: User has Troy Terry (ranked ~50-80)
        Bad recommendation: Connor McDavid, Nathan MacKinnon (rank 1-5) - unrealistic
        Good recommendation: Player ranked 60-120 with better underlying stats
        """
        from langchain_core.messages import HumanMessage

        # User asking about a mid-tier player
        input_text = "Troy Terry hasn't been performing well, who should I trade for?"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "").lower()

        # Check that obviously elite players are NOT recommended as targets
        elite_players = [
            "connor mcdavid",
            "nathan mackinnon",
            "nikita kucherov",
            "leon draisaitl",
            "auston matthews",
            "david pastrnak",
        ]

        # Count how many elite players are recommended
        elite_recommendations = sum(1 for player in elite_players if player in response_text)

        # Should not have multiple elite players as trade targets
        # (One mention might be for comparison context, but not as trade targets)
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
        """
        Trade targets should have upside indicators mentioned:
        - Negative goals above expected (due for regression UP)
        - Strong possession metrics (Fenwick > 52%)
        - Good ice time / line deployment
        - Favorable schedule
        """
        from langchain_core.messages import HumanMessage

        input_text = "I want to trade away a struggling player, find me undervalued targets"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "").lower()

        # Response should mention upside indicators
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

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_trade_targets_have_worse_or_similar_rank(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        """
        Trade targets should be realistic - players ranked similarly or worse,
        not players ranked significantly better who would never be traded 1-for-1.

        Uses LLM-as-judge to evaluate if recommendations are realistic.
        """
        from agentevals.trajectory.llm import create_trajectory_llm_as_judge
        from langchain_core.messages import HumanMessage

        input_text = "Who should I trade Troy Terry for? He's ranked around 70."
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        response_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey trade recommendation is REALISTIC:

            Context: The user has Troy Terry, a player ranked around 70th in fantasy hockey.
            They are looking for trade targets.

            A GOOD recommendation should suggest:
            1. Players ranked WORSE or SIMILAR (rank 50-150) but with better underlying stats
            2. Players who are undervalued/underperforming their expected stats
            3. Realistic 1-for-1 trade targets, not elite superstars

            A BAD recommendation suggests:
            1. Elite players ranked 1-20 (McDavid, MacKinnon, Kucherov, etc.) - UNREALISTIC
            2. Players obviously better by every metric with no explanation of why they'd be traded
            3. No mention of WHY these players are obtainable (undervalued, struggling, etc.)

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 if recommendations are realistic undervalued targets.
            Score 0.5 if mixed - some realistic, some unrealistic.
            Score 0.0 if recommending obviously better players that wouldn't be traded 1-for-1.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = response_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.7, (
            f"Trade recommendations should be realistic. Score: {eval_dict['score']}. "
            f"Comment: {eval_dict.get('comment', 'No comment')}"
        )


class TestTradeAgentUndervaluedIntegration:
    """
    Tests for the trade agent's integration with undervalued player scoring.

    Verifies that when looking for trade targets, the agent considers
    and mentions undervalued scores and reasons.
    """

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
        """Verify trade response includes undervalued player analysis."""
        mock_user_state["messages"] = [HumanMessage(content=trade_for_input)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        response_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey trade analysis response includes proper undervalued player analysis:

            1. Does it mention expected goals (xGoals) or goals above expected?
            2. Does it mention possession metrics (Fenwick%, Corsi%)?
            3. Does it explain why certain players might be undervalued or due for regression?
            4. Does it provide specific numbers/stats to support the analysis?

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 if includes strong undervalued analysis with specific stats.
            Score 0.5 if mentions some advanced stats but lacking depth.
            Score 0.0 if only uses basic stats or rank comparisons.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = response_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"Response should include undervalued analysis: {eval_dict.get('comment', eval_dict)}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_prioritizes_high_undervalued_score_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        """Verify agent prioritizes players with high undervalued scores."""
        input_text = "Find me a player who is shooting below their expected goals rate"
        mock_user_state["messages"] = [HumanMessage(content=input_text)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "").lower()

        # Should mention regression-related concepts
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
