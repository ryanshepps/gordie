"""LLM-as-Judge response quality evals for fantasy hockey agent."""

from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


class TestPersona:
    """Test that the agent maintains the 'Gordie' persona across different scenarios.

    Gordie should be:
    - Tough but friendly
    - Uses hockey/sports slang
    - Direct and helpful
    - Conversational, not robotic
    """

    @pytest.fixture
    def persona_evaluator(self):
        """Create a reusable persona evaluator."""
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response maintains the "Gordie" persona - a tough but friendly fantasy hockey assistant who uses sports slang and short sentences.

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 if tone is conversational and helpful (not robotic/formal), 0.5 if mixed, 0.0 if robotic.
            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @pytest.mark.parametrize(
        "user_message,scenario",
        [
            ("What do you think about my roster?", "roster_review"),
            ("Hey, who should I pick up this week?", "casual_greeting"),
            ("My team is losing, what should I do?", "frustrated_user"),
            ("Can you explain what Corsi means?", "technical_question"),
        ],
    )
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_persona_consistency_across_scenarios(
        self,
        mock_user_state,
        mock_yahoo_tools,
        persona_evaluator,
        user_message: str,
        scenario: str,
    ):
        """Verify the agent maintains the 'Gordie' persona across different user interactions."""
        mock_user_state["messages"] = [HumanMessage(content=user_message)]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        assert "error" not in response_text.lower() and "couldn't process" not in response_text.lower(), (
            f"Agent returned error response in {scenario} scenario: {response_text[:500]}"
        )

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = persona_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"Persona inconsistent in {scenario} scenario: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )
