"""Unit tests for the SMS response flow.

Verifies observable behavior:
- response_node sends SMS response via SmsService for SMS channel
- Email dispatch is unaffected
"""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState
from data.models import Medium
from server.adapters.base import AdapterRegistry, ChannelConstraints, MessageFormat


class FakeAdapter:
    medium = Medium.SMS

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    @property
    def constraints(self) -> ChannelConstraints:
        return ChannelConstraints(max_length=800, message_format=MessageFormat.PLAIN_TEXT)

    def send(self, external_id: str, text: str, state: AgentState) -> None:
        self.sent.append((external_id, text))


class TestResponseNodeSmsDispatch:
    """Verify response_node sends the final AI message as SMS."""

    def test_sends_final_ai_message_as_sms(self):
        """SMS response_node should send the last AI message via SmsService."""
        from agent.response_node import make_response_node

        adapter = FakeAdapter()
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

    def test_logs_warning_when_no_ai_message(self):
        """SMS response_node should warn when there's no AI message to send."""
        from agent.response_node import make_response_node

        adapter = FakeAdapter()
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

    def test_email_dispatches_normally(self):
        """Email channel dispatches through the registry adapter."""
        from agent.response_node import make_response_node

        adapter = FakeAdapter()
        adapter.medium = Medium.EMAIL
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
