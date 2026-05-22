"""Tests for SMS channel dispatch."""

from unittest.mock import MagicMock, patch

from agent.agent_state import AgentState
from server.adapters.sms_adapter import SmsAdapter


class TestSendSmsResponse:
    def test_sends_sms_for_short_message(self):
        """Short plain message is sent as-is."""
        state: AgentState = {"messages": []}

        mock_result = MagicMock(success=True, batch_id="batch-1")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with patch("server.sms_service.SmsService", return_value=mock_service):
            SmsAdapter().send("+15551234567", "Hello from Gordie!", state)

        mock_service.send_sms.assert_called_once()
        call_args = mock_service.send_sms.call_args
        assert call_args[0][0] == "+15551234567"
        assert call_args[0][1] == "Hello from Gordie!"

    def test_sends_long_message_as_is(self):
        """Long messages are sent without truncation (no web URL fallback)."""
        state: AgentState = {"messages": []}

        long_message = "A " * 200  # 400 chars

        mock_result = MagicMock(success=True, batch_id="batch-2")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with patch("server.sms_service.SmsService", return_value=mock_service):
            SmsAdapter().send("+15551234567", long_message, state)

        mock_service.send_sms.assert_called_once()

    def test_strips_markdown(self):
        """SMS sends plain text."""
        state: AgentState = {"messages": []}
        mock_result = MagicMock(success=True, batch_id="batch-3")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with patch("server.sms_service.SmsService", return_value=mock_service):
            SmsAdapter().send("+15551234567", "**Hello** [link](https://example.com)", state)

        assert mock_service.send_sms.call_args[0][1] == "Hello link"
