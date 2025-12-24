"""Player drop decision evals for fantasy hockey agent."""

from typing import Any, cast

from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node


class TestPlayerDropDecision:
    """
    Test: "Should I drop Timo Meier?"

    Expected Analysis:
    - Current production (goals, assists, points)
    - Advanced stats (xGoals vs actual goals, Fenwick%, Corsi%)
    - Upcoming schedule (games this week/next week)
    - Clear recommendation with reasoning

    Note: Some tests require an authenticated user. When no auth token exists,
    the agent correctly routes to onboarding - this is expected behavior.
    """

    def test_response_gives_recommendation_with_stats_and_schedule(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        """Verify response gives a clear drop/hold recommendation with stats and schedule context."""
        mock_user_state["messages"] = [HumanMessage(content="Should I drop Timo Meier?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        response_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate this fantasy hockey drop recommendation:

            User asked: "Should I drop Timo Meier?"

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Gives a clear yes/no/hold recommendation
            2. Cites specific stats or reasoning (goals, points, advanced stats like xGoals, Corsi, Fenwick)
            3. Considers schedule context (upcoming games, games this week, team schedule)
            4. Provides actionable advice

            Score 1.0 if all criteria met, 0.5 if mostly met (recommendation + stats OR schedule), 0.0 if vague/missing reasoning.
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
        assert eval_dict["score"] >= 0.5, f"Weak reasoning: {eval_dict.get('comment', eval_dict)}"
