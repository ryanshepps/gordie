"""Unit tests for adapter-backed response dispatch."""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState
from data.models import Medium
from server.adapters.base import AdapterRegistry, ChannelConstraints, MessageFormat


class FakeAdapter:
    def __init__(self, medium: Medium) -> None:
        self.medium = medium
        self.sent: list[tuple[str, str]] = []

    @property
    def constraints(self) -> ChannelConstraints:
        return ChannelConstraints(max_length=800, message_format=MessageFormat.PLAIN_TEXT)

    def send(self, external_id: str, text: str, state: AgentState) -> None:
        self.sent.append((external_id, text))


class TestResponseNodeDispatch:
    def test_sends_final_ai_message_as_sms(self) -> None:
        from agent.response_node import make_response_node

        adapter = FakeAdapter(Medium.SMS)
        response_node = make_response_node(AdapterRegistry({Medium.SMS: adapter}))
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

        with patch("agent.response_node._store_conversation_memory"):
            result = response_node(state)

        assert adapter.sent == [("+15551234567", "Go with Matthews tonight.")]
        assert result.goto == "__end__"

    def test_dispatches_final_ai_message_as_discord(self) -> None:
        from agent.response_node import make_response_node

        adapter = FakeAdapter(Medium.DISCORD)
        response_node = make_response_node(AdapterRegistry({Medium.DISCORD: adapter}))
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews tonight."),
            ],
            "channel": Medium.DISCORD,
            "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
            "user_id": "user-1",
            "external_id": "discord-user-1",
        }

        with patch("agent.response_node._store_conversation_memory"):
            result = response_node(state)

        assert adapter.sent == [("discord-user-1", "Go with Matthews tonight.")]
        assert result.goto == "__end__"

    def test_skips_adapter_dispatch_when_state_disables_it(self) -> None:
        from agent.response_node import make_response_node

        adapter = FakeAdapter(Medium.DISCORD)
        response_node = make_response_node(AdapterRegistry({Medium.DISCORD: adapter}))
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews tonight."),
            ],
            "channel": Medium.DISCORD,
            "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
            "user_id": "user-1",
            "external_id": "discord-user-1",
            "dispatch_response": False,
        }

        with patch("agent.response_node._store_conversation_memory"):
            result = response_node(state)

        assert adapter.sent == []
        assert result.goto == "__end__"

    def test_logs_warning_when_no_ai_message(self) -> None:
        from agent.response_node import make_response_node

        adapter = FakeAdapter(Medium.SMS)
        response_node = make_response_node(AdapterRegistry({Medium.SMS: adapter}))
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
            ],
            "channel": Medium.SMS,
            "thread_id": "thread-1",
            "user_id": "user-1",
            "external_id": "+15551234567",
        }

        with patch("agent.response_node._store_conversation_memory"):
            result = response_node(state)

        assert adapter.sent == []
        assert result.goto == "__end__"

    def test_email_dispatches_normally(self) -> None:
        from agent.response_node import make_response_node

        adapter = FakeAdapter(Medium.EMAIL)
        response_node = make_response_node(AdapterRegistry({Medium.EMAIL: adapter}))
        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews."),
            ],
            "channel": Medium.EMAIL,
            "thread_id": "test-thread-123",
            "user_id": "user-1",
            "external_id": "test@example.com",
            "original_subject": "Fantasy Hockey Help",
        }

        with patch("agent.response_node._store_conversation_memory"):
            result = response_node(state)

        assert adapter.sent == [("test@example.com", "Go with Matthews.")]
        assert result.goto == "__end__"
