"""Agent evals for SMS channel flow.

Black-box evals that verify observable SMS behavior:
- Final response is short, plain text, conversational
- Same core recommendation as email, different delivery
"""

import re
import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

MARKDOWN_PATTERNS = (
    re.compile(r"\*\*"),
    re.compile(r"^#{1,6}\s", re.MULTILINE),
    re.compile(r"```"),
    re.compile(r"\|\s"),
)
SMS_MAX_LENGTH = 800


@pytest.fixture
def sms_user_state():
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


class TestSmsMessageQuality:

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
        self, sms_user_state, mock_yahoo_tools, user_message
    ):
        sms_user_state["messages"] = [HumanMessage(content=user_message)]
        result = supervisor_node(sms_user_state)

        update = result.update or {}
        response = update.get("response", "")

        assert response, "SMS agent produced no response"

        for pattern in MARKDOWN_PATTERNS:
            assert not pattern.search(response), (
                f"SMS response contains markdown ({pattern.pattern}): {response[:500]}"
            )

        assert len(response) < SMS_MAX_LENGTH, (
            f"SMS response too long ({len(response)} chars, max {SMS_MAX_LENGTH}): {response[:500]}"
        )


class TestSmsVsEmailConsistency:

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
        question = "Should I trade away Draisaitl? What should I target?"

        sms_user_state["messages"] = [HumanMessage(content=question)]
        sms_result = supervisor_node(sms_user_state)
        sms_update = sms_result.update or {}
        sms_response = cast(dict[str, Any], sms_update).get("response", "")

        assert sms_response, "SMS agent produced no output"

        email_user_state["messages"] = [HumanMessage(content=question)]
        email_result = supervisor_node(email_user_state)
        email_update = email_result.update or {}
        email_response = cast(dict[str, Any], email_update).get("response", "")

        assert email_response, "Email agent produced no output"

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
        assert eval_dict["score"] >= 0.5, (
            f"SMS and email should give same core answer: {eval_dict.get('comment')}\n"
            f"SMS: {sms_response[:300]}\n"
            f"Email: {email_response[:300]}"
        )
