"""Data quality node evals for fantasy hockey agent."""

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.agent_state import AgentState
from agent.data_quality_node import data_quality_node
from tests.evals.conftest import retry_on_rate_limit

RESPONSE_MISSING_GP_CONTEXT = (
    "Based on the stats, I'd recommend dropping Timo Meier and picking up "
    "Teuvo Teravainen. Teravainen has 35 points this season compared to "
    "Meier's 18 points. Teravainen also has stronger underlying numbers "
    "with 12.5 expected goals vs Meier's 7.2 expected goals. "
    "Teravainen is clearly the more productive player right now."
)

RESPONSE_WITH_GP_CONTEXT = (
    "Based on the stats, I'd recommend holding Timo Meier for now. "
    "While Teravainen has 35 points compared to Meier's 18, keep in mind "
    "that Meier has only played 28 games due to injury while Teravainen "
    "has played 55. On a per-game basis, Meier is actually producing at "
    "a comparable rate (0.64 pts/gp vs 0.64 pts/gp). With Meier healthy "
    "and ramping up, his production should climb."
)


def _make_state(ai_response: str, retries: int = 0) -> AgentState:
    return AgentState(
        messages=[
            HumanMessage(content="Should I drop Timo Meier for Teuvo Teravainen?"),
            AIMessage(content=ai_response),
        ],
        user_email="test@example.com",
        thread_id=str(uuid.uuid4()),
        data_quality_retries=retries,
    )


@pytest.mark.integration
class TestDataQualityGamesPlayed:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_flags_response_missing_games_played_context(self):
        state = _make_state(RESPONSE_MISSING_GP_CONTEXT)

        result = data_quality_node(state)

        assert result.goto == "supervisor", (
            "Expected routing back to supervisor when GP context is missing"
        )
        update = result.update or {}
        feedback_messages = [
            m
            for m in update.get("messages", [])
            if isinstance(m, SystemMessage) and "DATA QUALITY" in m.content
        ]
        assert len(feedback_messages) == 1
        assert update.get("data_quality_retries") == 1

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_passes_response_with_games_played_context(self):
        state = _make_state(RESPONSE_WITH_GP_CONTEXT)

        result = data_quality_node(state)

        assert result.goto == "voice_rewrite", "Expected pass-through when GP context is present"

    def test_skips_check_when_retry_limit_reached(self):
        state = _make_state(RESPONSE_MISSING_GP_CONTEXT, retries=1)

        result = data_quality_node(state)

        assert result.goto == "voice_rewrite", "Expected pass-through when retry limit is reached"
