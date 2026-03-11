"""Unit tests for the SMS response flow.

Verifies observable behavior:
- response_node sends SMS response via SmsService for SMS channel
- Email dispatch is unaffected
"""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState


class TestResponseNodeSmsDispatch:
    """Verify response_node sends the final AI message as SMS."""

    def test_sends_final_ai_message_as_sms(self):
        """SMS response_node should send the last AI message via SmsService."""
        from agent.response_node import response_node

        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
                AIMessage(content="Go with Matthews tonight."),
            ],
            "channel": "sms",
            "thread_id": "sms:+15551234567:abc123",
            "user_email": "test@example.com",
        }

        with (
            patch("agent.response_node.send_sms_response") as mock_sms,
            patch("agent.response_node._store_conversation_memory"),
        ):
            result = response_node(state)

        mock_sms.assert_called_once_with(state, "Go with Matthews tonight.")
        assert result.goto == "__end__"

    def test_logs_warning_when_no_ai_message(self):
        """SMS response_node should warn when there's no AI message to send."""
        from agent.response_node import response_node

        state: AgentState = {
            "messages": [
                HumanMessage(content="Who should I start?"),
            ],
            "channel": "sms",
            "thread_id": "sms:+15551234567:abc123",
            "user_email": "test@example.com",
        }

        with (
            patch("agent.response_node.send_sms_response") as mock_sms,
            patch("agent.response_node._store_conversation_memory"),
        ):
            result = response_node(state)

        mock_sms.assert_not_called()
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


