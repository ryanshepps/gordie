"""Agent evals for SMS channel flow.

Black-box evals that verify observable SMS behavior:
- Agent sends ack via send_acknowledgement before doing heavy work
- Final response is short, plain text, conversational
- Same core recommendation as email, different delivery
"""

import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import AIMessage, HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


@pytest.fixture
def sms_user_state():
    """User state configured for SMS channel."""
    phone = "+15551234567"
    thread_id = f"sms:{phone}:{uuid.uuid4()}"
    return {
        "messages": [],
        "user_email": "test@example.com",
        "league_id": "12345",
        "team_id": "1",
        "thread_id": thread_id,
        "channel": "sms",
        "user_teams": [
            {
                "league_id": "12345",
                "team_id": "1",
                "team_name": "Test Team",
                "game_key": "nhl.l.12345",
                "league_name": "Test League",
            }
        ],
    }


@pytest.fixture
def email_user_state():
    """User state configured for email channel."""
    return {
        "messages": [],
        "user_email": "test@example.com",
        "league_id": "12345",
        "team_id": "1",
        "thread_id": str(uuid.uuid4()),
        "channel": "email",
        "user_teams": [
            {
                "league_id": "12345",
                "team_id": "1",
                "team_name": "Test Team",
                "game_key": "nhl.l.12345",
                "league_name": "Test League",
            }
        ],
    }


def _get_send_acknowledgement_texts(messages: list[Any]) -> list[str]:
    """Extract the message text from each send_acknowledgement tool call."""
    texts = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "send_acknowledgement":
                    texts.append(tc.get("args", {}).get("message", ""))
    return texts


def _get_ordered_tool_names(messages: list[Any]) -> list[str]:
    """Get tool call names in the order they were invoked."""
    names = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                names.append(tc.get("name", ""))
    return names


class TestSmsAckThenAnswer:
    """The agent should ack before doing heavy work, then send its answer via send_acknowledgement."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_ack_before_data_tools(
        self, sms_user_state, mock_yahoo_tools
    ):
        """First tool call should be send_acknowledgement (ack), before any data-fetching tools."""
        sms_user_state["messages"] = [
            HumanMessage(content="Who should I grab off waivers?")
        ]
        result = supervisor_node(sms_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_names = _get_ordered_tool_names(result_messages)

        if not tool_names:
            pytest.skip("Agent made no tool calls")

        data_tools = {"trade", "available_players", "search_past_conversations"}
        first_data_tool_idx = next(
            (i for i, name in enumerate(tool_names) if name in data_tools),
            None,
        )
        first_send_idx = next(
            (i for i, name in enumerate(tool_names) if name == "send_acknowledgement"),
            None,
        )

        assert first_send_idx is not None, (
            f"Agent should use send_acknowledgement on SMS. Tool order: {tool_names}"
        )

        if first_data_tool_idx is not None:
            assert first_send_idx < first_data_tool_idx, (
                f"Agent should ack via send_acknowledgement before calling data tools. "
                f"Tool order: {tool_names}"
            )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_email_does_not_use_send_acknowledgement(
        self, email_user_state, mock_yahoo_tools
    ):
        """Email channel should not use send_acknowledgement at all."""
        email_user_state["messages"] = [
            HumanMessage(content="Who should I grab off waivers?")
        ]
        result = supervisor_node(email_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        sms_texts = _get_send_acknowledgement_texts(result_messages)

        assert len(sms_texts) == 0, "Email agent should NOT use send_acknowledgement tool"


class TestSmsMessageQuality:
    """SMS final response should be short, plain text, and sound like a real person texting."""

    @pytest.fixture
    def sms_quality_evaluator(self):
        return create_trajectory_llm_as_judge(
            prompt="""You are evaluating an SMS text message from a fantasy hockey assistant named Gordie.

            This is the final response sent to the user's phone. Evaluate ALL of these criteria:

            1. CONVERSATIONAL TONE: Message sounds like a real person texting — casual, uses contractions,
               punchy sentences. NOT formal, NOT robotic, NOT like a report or email.
            2. PLAIN TEXT: No markdown formatting (no **, ##, tables, code blocks, bullet lists).
               Stats should be inline: "12 goals in his last 10" not "| Goals | 12 |"
            3. CONCISE: Message should be brief. No walls of text. Key info only.
            4. SPORTS-KNOWLEDGEABLE: Includes specific, relevant stats or reasoning — not vague.

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 ONLY if ALL four criteria are met convincingly.
            Score 0.5 if two or three are met but others fail.
            Score 0.0 if it reads like an email, a formal report, or contains markdown.
            One sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    @pytest.mark.parametrize(
        "user_message",
        [
            "Should I start Matthews or McDavid tonight?",
            "My team's been losing a lot, any advice?",
            "Someone offered me Draisaitl for my Rantanen straight up",
        ],
    )
    def test_sms_reads_like_texting(
        self, sms_user_state, mock_yahoo_tools, sms_quality_evaluator, user_message
    ):
        """Every SMS response should read like a real person texting about fantasy hockey."""
        sms_user_state["messages"] = [HumanMessage(content=user_message)]
        result = supervisor_node(sms_user_state)

        update = result.update or {}
        response = cast(dict[str, Any], update).get("response", "")

        if not response:
            pytest.skip("No final response to evaluate")

        output_messages = [{"role": "assistant", "content": response}]

        eval_result = sms_quality_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.8, (
            f"SMS should read like texting a friend: {eval_dict.get('comment')}\n"
            f"Response: {response[:500]}"
        )


class TestSmsVsEmailConsistency:
    """Same question on SMS and email should give the same core recommendation."""

    @pytest.fixture
    def consistency_evaluator(self):
        return create_trajectory_llm_as_judge(
            prompt="""Compare an SMS response and an email response to the SAME fantasy hockey question.

            The SMS will be shorter and more casual. The email will be longer with more detail.
            That difference in FORMAT is expected and correct.

            Evaluate ONLY whether they give the SAME CORE RECOMMENDATION:
            1. Do they recommend the same player(s) or course of action?
            2. Are the key stats consistent (not contradictory)?
            3. Would a user get the same advice from both channels?

            <trajectory>
            {outputs}
            </trajectory>

            Score 1.0 if the core recommendation and key facts are consistent.
            Score 0.5 if the direction is similar but specifics diverge.
            Score 0.0 if they give contradictory advice.
            One sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_same_question_same_recommendation(
        self, sms_user_state, email_user_state, mock_yahoo_tools, consistency_evaluator
    ):
        """SMS and email should arrive at the same core answer for identical questions."""
        question = "Should I trade away Draisaitl? What should I target?"

        # SMS
        sms_user_state["messages"] = [HumanMessage(content=question)]
        sms_result = supervisor_node(sms_user_state)
        sms_update = sms_result.update or {}
        sms_response = cast(dict[str, Any], sms_update).get("response", "")

        if not sms_response:
            pytest.skip("SMS agent produced no output")

        # Email
        email_user_state["messages"] = [HumanMessage(content=question)]
        email_result = supervisor_node(email_user_state)
        email_update = email_result.update or {}
        email_response = cast(dict[str, Any], email_update).get("response", "")

        if not email_response:
            pytest.skip("Email agent produced no output")

        combined = (
            f"SMS response:\n{sms_response}\n\n"
            f"Email response:\n{email_response}"
        )
        output_messages = [{"role": "assistant", "content": combined}]

        eval_result = consistency_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.8, (
            f"SMS and email should give same core answer: {eval_dict.get('comment')}\n"
            f"SMS: {sms_response[:300]}\n"
            f"Email: {email_response[:300]}"
        )
