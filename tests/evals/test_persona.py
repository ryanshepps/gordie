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


class TestPersonaEntertainment:
    """Test that Gordie's new persona delivers spicy, entertaining responses.

    These evals exist to preview the persona output so you can tune the prompts.
    Run with `uv run pytest tests/evals/test_persona.py::TestPersonaEntertainment -v -s`
    to see the full responses.
    """

    @pytest.fixture
    def entertainment_evaluator(self):
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey assistant response is entertaining and has personality.

            <trajectory>
            {outputs}
            </trajectory>

            Check for these traits:
            1. Uses colorful language, slang, or vivid metaphors (not generic/corporate)
            2. Has a strong voice — reads like a real person with opinions, not a bland assistant
            3. Still delivers useful fantasy hockey advice underneath the personality

            Score 1.0 if all three traits are present, 0.5 if the response has some personality but is still partly bland, 0.0 if it reads like a generic AI assistant.
            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @pytest.fixture
    def roast_evaluator(self):
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey assistant roasts or trash-talks underperforming players.

            <trajectory>
            {outputs}
            </trajectory>

            The response should contain colorful, funny criticism of players who are struggling — not just dry stats. Look for vivid language like insults, metaphors, or jokes about how bad someone is playing.

            Score 1.0 if there's clear entertaining trash talk about struggling players, 0.5 if mildly critical but bland, 0.0 if it's polite and diplomatic about poor performance.
            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @pytest.fixture
    def buddy_ribbing_evaluator(self):
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this fantasy hockey assistant gives the user friendly trash talk or ribbing.

            <trajectory>
            {outputs}
            </trajectory>

            The response should playfully tease or rib the user like a friend would — questioning their decision, giving them a hard time, or joking about a bad idea. It should NOT be mean or condescending.

            Score 1.0 if the response clearly ribs/teases the user in a friendly way, 0.5 if slightly teasing but mostly neutral, 0.0 if it's purely polite and supportive with no ribbing.
            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_entertaining_roster_review(
        self,
        mock_user_state,
        mock_yahoo_tools,
        entertainment_evaluator,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Give me an honest review of my roster. Don't hold back.")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")
        print(f"\n{'='*60}\nROSTER REVIEW RESPONSE:\n{'='*60}\n{response_text}\n{'='*60}")

        eval_result = entertainment_evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )
        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        print(f"Entertainment score: {eval_dict['score']} — {eval_dict.get('comment')}")
        assert eval_dict["score"] >= 0.5, (
            f"Response lacked entertainment: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_roasts_cold_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
        roast_evaluator,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Timo Meier has been terrible for me. What should I do with him?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")
        print(f"\n{'='*60}\nCOLD PLAYER ROAST RESPONSE:\n{'='*60}\n{response_text}\n{'='*60}")

        eval_result = roast_evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )
        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        print(f"Roast score: {eval_dict['score']} — {eval_dict.get('comment')}")
        assert eval_dict["score"] >= 0.5, (
            f"Response didn't roast the cold player: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_buddy_ribbing_on_bad_idea(
        self,
        mock_user_state,
        mock_yahoo_tools,
        buddy_ribbing_evaluator,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Should I drop Connor McDavid? He's been kinda quiet lately.")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")
        print(f"\n{'='*60}\nBUDDY RIBBING RESPONSE:\n{'='*60}\n{response_text}\n{'='*60}")

        eval_result = buddy_ribbing_evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )
        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        print(f"Buddy ribbing score: {eval_dict['score']} — {eval_dict.get('comment')}")
        assert eval_dict["score"] >= 0.5, (
            f"Response didn't rib the user: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_hypes_hot_players(
        self,
        mock_user_state,
        mock_yahoo_tools,
        entertainment_evaluator,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="How's McDavid been doing? Give me the rundown.")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")
        print(f"\n{'='*60}\nHOT PLAYER HYPE RESPONSE:\n{'='*60}\n{response_text}\n{'='*60}")

        eval_result = entertainment_evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )
        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        print(f"Entertainment score: {eval_dict['score']} — {eval_dict.get('comment')}")
        assert eval_dict["score"] >= 0.5, (
            f"Response lacked hype energy: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_pickup_recommendation_has_energy(
        self,
        mock_user_state,
        mock_yahoo_tools,
        entertainment_evaluator,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Who should I pick up from waivers right now?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")
        print(f"\n{'='*60}\nPICKUP RECOMMENDATION RESPONSE:\n{'='*60}\n{response_text}\n{'='*60}")

        eval_result = entertainment_evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )
        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        print(f"Entertainment score: {eval_dict['score']} — {eval_dict.get('comment')}")
        assert eval_dict["score"] >= 0.5, (
            f"Response lacked energy: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )
