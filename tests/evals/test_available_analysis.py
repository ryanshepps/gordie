"""Evals for available players subagent - streaming and pickup/drop analysis."""

import json
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


def _build_mock_comprehensive_stats() -> str:
    """Build mock response for get_comprehensive_player_stats_internal."""
    return json.dumps({
        "Teuvo Teravainen": {
            "status": "success",
            "name": "Teuvo Teravainen",
            "team": "CHI",
            "position": "RW",
            "games_played": 35,
            "goals": 12,
            "assists": 20,
            "points": 32,
            "points_per_game": 0.91,
            "toi_per_game_minutes": 18.5,
            "x_goals": 10.5,
            "goals_above_expected": 1.5,
            "fenwick_pct": 52.3,
            "corsi_pct": 51.8,
            "yahoo_rank": 85,
            "games_remaining_this_week": 3,
            "games_next_week": 4,
            "estimated_line_number": 2,
            "undervalued_score": 4.5,
            "undervalued_reasons": ["Strong possession: 52.3% Fenwick", "Good schedule"],
        },
        "Brock Boeser": {
            "status": "success",
            "name": "Brock Boeser",
            "team": "VAN",
            "position": "RW",
            "games_played": 38,
            "goals": 15,
            "assists": 18,
            "points": 33,
            "points_per_game": 0.87,
            "toi_per_game_minutes": 17.2,
            "x_goals": 12.0,
            "goals_above_expected": 3.0,
            "fenwick_pct": 51.5,
            "corsi_pct": 50.8,
            "yahoo_rank": 72,
            "games_remaining_this_week": 2,
            "games_next_week": 3,
            "estimated_line_number": 1,
            "undervalued_score": 3.2,
            "undervalued_reasons": ["First line deployment"],
        },
        "Jake Guentzel": {
            "status": "success",
            "name": "Jake Guentzel",
            "team": "TBL",
            "position": "LW",
            "games_played": 40,
            "goals": 18,
            "assists": 22,
            "points": 40,
            "points_per_game": 1.0,
            "toi_per_game_minutes": 19.5,
            "x_goals": 16.0,
            "goals_above_expected": 2.0,
            "fenwick_pct": 54.1,
            "corsi_pct": 53.2,
            "yahoo_rank": 45,
            "games_remaining_this_week": 4,
            "games_next_week": 3,
            "estimated_line_number": 1,
            "undervalued_score": 5.8,
            "undervalued_reasons": ["Elite possession", "Favorable schedule"],
        },
        "Filip Forsberg": {
            "status": "success",
            "name": "Filip Forsberg",
            "team": "NSH",
            "position": "LW",
            "games_played": 36,
            "goals": 20,
            "assists": 15,
            "points": 35,
            "points_per_game": 0.97,
            "toi_per_game_minutes": 18.8,
            "x_goals": 18.0,
            "goals_above_expected": 2.0,
            "fenwick_pct": 50.5,
            "corsi_pct": 49.8,
            "yahoo_rank": 55,
            "games_remaining_this_week": 3,
            "games_next_week": 4,
            "estimated_line_number": 1,
            "undervalued_score": 4.0,
            "undervalued_reasons": ["First line deployment"],
        },
        "Kirill Kaprizov": {
            "status": "success",
            "name": "Kirill Kaprizov",
            "team": "MIN",
            "position": "LW",
            "games_played": 42,
            "goals": 25,
            "assists": 30,
            "points": 55,
            "points_per_game": 1.31,
            "toi_per_game_minutes": 21.5,
            "x_goals": 22.0,
            "goals_above_expected": 3.0,
            "fenwick_pct": 55.2,
            "corsi_pct": 54.5,
            "yahoo_rank": 12,
            "games_remaining_this_week": 2,
            "games_next_week": 4,
            "estimated_line_number": 1,
            "undervalued_score": 6.5,
            "undervalued_reasons": ["Elite possession", "Top-line deployment"],
        },
        # Roster players (from conftest mock_roster_response)
        "Timo Meier": {
            "status": "success",
            "name": "Timo Meier",
            "team": "NJD",
            "position": "LW",
            "games_played": 38,
            "goals": 10,
            "assists": 18,
            "points": 28,
            "points_per_game": 0.74,
            "toi_per_game_minutes": 16.5,
            "x_goals": 14.0,
            "goals_above_expected": -4.0,
            "fenwick_pct": 48.2,
            "corsi_pct": 47.5,
            "yahoo_rank": 120,
            "games_remaining_this_week": 2,
            "games_next_week": 3,
            "estimated_line_number": 2,
            "undervalued_score": -2.5,
            "undervalued_reasons": ["Overperforming", "Poor possession"],
        },
        "Leon Draisaitl": {
            "status": "success",
            "name": "Leon Draisaitl",
            "team": "EDM",
            "position": "C",
            "games_played": 40,
            "goals": 22,
            "assists": 23,
            "points": 45,
            "points_per_game": 1.13,
            "toi_per_game_minutes": 21.0,
            "x_goals": 20.0,
            "goals_above_expected": 2.0,
            "fenwick_pct": 54.8,
            "corsi_pct": 55.2,
            "yahoo_rank": 8,
            "games_remaining_this_week": 3,
            "games_next_week": 4,
            "estimated_line_number": 1,
            "undervalued_score": 5.0,
            "undervalued_reasons": ["Elite possession", "Top-line deployment"],
        },
        "Connor McDavid": {
            "status": "success",
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
            "games_played": 40,
            "goals": 28,
            "assists": 24,
            "points": 52,
            "points_per_game": 1.30,
            "toi_per_game_minutes": 22.5,
            "x_goals": 25.0,
            "goals_above_expected": 3.0,
            "fenwick_pct": 57.5,
            "corsi_pct": 58.1,
            "yahoo_rank": 1,
            "games_remaining_this_week": 3,
            "games_next_week": 4,
            "estimated_line_number": 1,
            "undervalued_score": 7.0,
            "undervalued_reasons": ["Best player in the world", "Elite everything"],
        },
    })


@pytest.mark.integration
class TestAvailablePlayersWorkflow:
    """Test basic workflow and response structure for available players analysis."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_response_includes_fa_and_waiver_recommendations(
        self, mock_user_state, mock_yahoo_tools, mocker
    ):
        """Verify response separates FA and waiver recommendations."""
        # Mock the stats enrichment to return realistic data
        mocker.patch(
            "tools.yahoo.get_available_players_with_stats.get_comprehensive_player_stats_internal",
            return_value=_build_mock_comprehensive_stats(),
        )

        # User asks for available players without specifying drop candidate
        user_input = "Who are the best available players I should pick up for streaming this week?"
        mock_user_state["messages"] = [HumanMessage(content=user_input)]

        # Invoke supervisor
        result = supervisor_node(mock_user_state)

        # Extract response
        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Create LLM-as-judge to evaluate response quality
        response_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey available players response meets these criteria:
1. Contains recommendations for both Free Agents (FA) and/or Waiver players
2. Clearly distinguishes between immediate adds (FA) and claim required (Waivers)
3. Includes specific player names as recommendations
4. References schedule or timing considerations

Score 1.0 if all criteria met, 0.5 if partially met (3/4), 0.0 if fewer met.
""",
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        eval_result = cast(
            dict[str, Any],
            cast(
                object,
                response_evaluator(
                    outputs=[{"role": "assistant", "content": response_text}],
                    reference_outputs=[],
                ),
            ),
        )

        assert eval_result["score"] >= 1, f"Response quality too low: {response_text}"


@pytest.mark.integration
class TestAvailablePlayersQuality:
    """Test quality of available player recommendations."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_schedule_comparison_critical_for_streaming(
        self, mock_user_state, mock_yahoo_tools, mocker
    ):
        """Verify recommendations heavily weight schedule for streaming strategy."""
        # Mock the stats enrichment to return realistic data
        mocker.patch(
            "tools.yahoo.get_available_players_with_stats.get_comprehensive_player_stats_internal",
            return_value=_build_mock_comprehensive_stats(),
        )

        user_input = "I need streaming options for this week - who has the best schedule?"
        mock_user_state["messages"] = [HumanMessage(content=user_input)]

        result = supervisor_node(mock_user_state)
        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Evaluate schedule emphasis
        schedule_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response emphasizes schedule considerations for streaming:
1. Mentions number of games (this week, next week, upcoming)
2. Compares schedules between recommended players
3. Explains how schedule impacts streaming value
4. Uses schedule as a key decision factor

Score 1.0 if all present, 0.7 if 3/4, 0.5 if 2/4, 0.0 if fewer.
""",
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        eval_result = cast(
            dict[str, Any],
            cast(
                object,
                schedule_evaluator(
                    outputs=[{"role": "assistant", "content": response_text}],
                    reference_outputs=[],
                ),
            ),
        )

        assert eval_result["score"] >= 1, f"Schedule emphasis too low: {response_text}"

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_peripherals_comparison(self, mock_user_state, mock_yahoo_tools, mocker):
        """Verify recommendations compare advanced stats (xGoals, Fenwick%, TOI)."""
        # Mock the stats enrichment to return realistic data
        mocker.patch(
            "tools.yahoo.get_available_players_with_stats.get_comprehensive_player_stats_internal",
            return_value=_build_mock_comprehensive_stats(),
        )

        user_input = "Who are the best available players based on advanced stats?"
        mock_user_state["messages"] = [HumanMessage(content=user_input)]

        result = supervisor_node(mock_user_state)
        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Evaluate advanced stats usage
        stats_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response uses advanced statistical analysis:
1. References expected goals (xGoals, xG) or similar metrics
2. Mentions possession metrics (Fenwick%, Corsi%, or similar)
3. Discusses time on ice (TOI) or deployment
4. Explains goals above expected (GAE) or regression potential

Score 1.0 if all present, 0.7 if 3/4, 0.5 if 2/4, 0.0 if fewer.
""",
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        eval_result = cast(
            dict[str, Any],
            cast(
                object,
                stats_evaluator(
                    outputs=[{"role": "assistant", "content": response_text}],
                    reference_outputs=[],
                ),
            ),
        )

        assert eval_result["score"] >= 1, f"Advanced stats usage too low: {response_text}"


@pytest.mark.integration
class TestAvailablePracticalScenarios:
    """Test practical streaming and pickup/drop scenarios."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_fa_vs_waiver_timing_for_streaming(self, mock_user_state, mock_yahoo_tools, mocker):
        """Verify response explains FA = immediate streaming, W = claim required."""
        # Mock the stats enrichment to return realistic data
        mocker.patch(
            "tools.yahoo.get_available_players_with_stats.get_comprehensive_player_stats_internal",
            return_value=_build_mock_comprehensive_stats(),
        )

        user_input = "What's the difference between free agents and waivers for streaming?"
        mock_user_state["messages"] = [HumanMessage(content=user_input)]

        result = supervisor_node(mock_user_state)
        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Evaluate FA/W timing explanation
        timing_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response clearly explains FA vs Waiver timing:
1. Explains that free agents (FA) can be added immediately
2. Explains that waivers (W) require a claim and processing period
3. Discusses the strategic implications for streaming
4. Provides clear actionable guidance on which to use

Score 1.0 if all criteria met (perfect explanation), 0.0 if unclear or missing.
""",
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        eval_result = cast(
            dict[str, Any],
            cast(
                object,
                timing_evaluator(
                    outputs=[{"role": "assistant", "content": response_text}],
                    reference_outputs=[],
                ),
            ),
        )

        assert eval_result["score"] >= 1, f"FA/W timing clarity too low: {response_text}"

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_user_specified_drop_candidate(self, mock_user_state, mock_yahoo_tools, mocker):
        """Verify agent handles user-specified drop candidate correctly."""
        # Mock the stats enrichment to return realistic data
        mocker.patch(
            "tools.yahoo.get_available_players_with_stats.get_comprehensive_player_stats_internal",
            return_value=_build_mock_comprehensive_stats(),
        )

        user_input = "Should I drop Timo Meier to pick up someone better?"
        mock_user_state["messages"] = [HumanMessage(content=user_input)]

        result = supervisor_node(mock_user_state)
        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Evaluate handling of specified drop
        drop_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly handles the specified drop candidate (Timo Meier):
1. Acknowledges Timo Meier as the potential drop
2. Analyzes Meier's stats/performance
3. Recommends specific replacement options
4. Compares replacements to Meier directly

Score 1.0 if all present, 0.7 if 3/4, 0.5 if 2/4, 0.0 if fewer.
""",
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        eval_result = cast(
            dict[str, Any],
            cast(
                object,
                drop_evaluator(
                    outputs=[{"role": "assistant", "content": response_text}],
                    reference_outputs=[],
                ),
            ),
        )

        assert eval_result["score"] >= 1, f"Drop candidate handling too low: {response_text}"
