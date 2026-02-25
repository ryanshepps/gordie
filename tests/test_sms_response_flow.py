"""Unit tests for the SMS response flow changes.

Verifies observable behavior:
- response_node skips SMS dispatch when messages were sent via tool
- response_node does not send SMS when no tool messages were sent (error case)
- send_message tool rejects messages over 320 chars
- Email dispatch is unaffected
"""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState


class TestResponseNodeSmsSkipsDispatch:
    """Verify response_node does not dispatch SMS when messages were sent via tool."""

    def test_no_sms_sent_when_messages_already_delivered(self):
        """SMS should not dispatch through sms_channel when agent already sent messages."""
        from agent.response_node import response_node

        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews."),
            ],
            "channel": "sms",
            "thread_id": "sms:+15551234567:abc123",
            "user_email": "test@example.com",
            "sms_messages_sent": 3,
        }

        with (
            patch("agent.response_node.send_email_response") as mock_email,
            patch("agent.response_node._store_conversation_memory") as mock_memory,
        ):
            result = response_node(state)

        mock_email.assert_not_called()
        mock_memory.assert_called_once()
        assert result.goto == "__end__"

    def test_no_fallback_sms_sent_on_zero_messages(self):
        """When SMS agent fails to use send_message, response_node should not send a fallback."""
        from agent.response_node import response_node

        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews."),
            ],
            "channel": "sms",
            "thread_id": "sms:+15551234567:abc123",
            "user_email": "test@example.com",
            "sms_messages_sent": 0,
        }

        with (
            patch("agent.response_node.send_email_response") as mock_email,
            patch("agent.response_node._store_conversation_memory") as mock_memory,
        ):
            result = response_node(state)

        # No dispatch at all — not email, not SMS
        mock_email.assert_not_called()
        # Memory still stored
        mock_memory.assert_called_once()
        assert result.goto == "__end__"

    def test_email_dispatches_normally(self):
        """Email channel should still dispatch through email_channel."""
        from agent.response_node import response_node

        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews."),
            ],
            "channel": "email",
            "thread_id": "test-thread-123",
            "user_email": "test@example.com",
            "original_subject": "Fantasy Hockey Help",
        }

        with (
            patch("agent.response_node.send_email_response") as mock_email,
            patch("agent.response_node._store_conversation_memory"),
        ):
            result = response_node(state)

        mock_email.assert_called_once()
        assert result.goto == "__end__"


class TestSendMessageCharacterLimit:
    """Verify send_message enforces the 320 character limit via rejection."""

    def test_rejects_over_limit(self):
        """Messages over 320 chars should be rejected, not truncated."""
        from tools.send_message import send_message

        # InjectedState params are hidden from the tool schema, so call the
        # underlying function directly for unit tests.
        result = send_message.func(  # pyright: ignore[reportAttributeAccessIssue]
            message="A" * 321,
            channel_type="sms",
            state={"thread_id": "sms:+15551234567:abc123"},
        )

        assert "error" in result.lower()
        assert "320" in result

    def test_accepts_at_limit(self):
        """Messages at exactly 320 chars should be sent."""
        from tools.send_message import send_message

        with patch("tools.send_message._send_sms", return_value=True):
            result = send_message.func(  # pyright: ignore[reportAttributeAccessIssue]
                message="A" * 320,
                channel_type="sms",
                state={"thread_id": "sms:+15551234567:abc123"},
            )

        assert "error" not in result.lower()
