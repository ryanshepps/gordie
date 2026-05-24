"""Unit tests for response finalization."""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState
from data.models import Medium


class TestResponseNodeFinalization:
    def test_finishes_after_ai_message_and_stores_memory(self) -> None:
        from agent.response_node import make_response_node

        response_node = make_response_node()
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews tonight."),
            ],
            "channel": Medium.SMS,
            "thread_id": "thread-1",
            "user_id": "user-1",
            "external_id": "+15551234567",
        }

        with patch("agent.response_node._store_conversation_memory") as store_memory:
            result = response_node(state)

        store_memory.assert_called_once_with(state, state["messages"])
        assert result.goto == "__end__"

    def test_skips_memory_when_no_ai_message(self) -> None:
        from agent.response_node import make_response_node

        response_node = make_response_node()
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
            ],
            "channel": Medium.SMS,
            "thread_id": "thread-1",
            "user_id": "user-1",
            "external_id": "+15551234567",
        }

        with patch("agent.response_node._store_conversation_memory") as store_memory:
            result = response_node(state)

        store_memory.assert_not_called()
        assert result.goto == "__end__"
