"""Tests for SMS channel dispatch."""

from unittest.mock import MagicMock, patch

from agent.agent_state import AgentState
from agent.channels.sms_channel import send_sms_response


class TestSendSmsResponse:
    def test_sends_sms_for_short_message(self):
        """Short plain message is sent as-is."""
        state: AgentState = {
            "messages": [],
            "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        }

        mock_result = MagicMock(success=True, batch_id="batch-1")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with (
            patch("server.sms_service.SmsService", return_value=mock_service),
            patch("data.thread_repository.ThreadRepository") as mock_repo,
        ):
            mock_repo.return_value.get_sms_external_id.return_value = "+15551234567"
            send_sms_response(state, "Hello from Gordie!")

        mock_service.send_sms.assert_called_once()
        call_args = mock_service.send_sms.call_args
        assert call_args[0][0] == "+15551234567"
        assert call_args[0][1] == "Hello from Gordie!"

    def test_sends_long_message_as_is(self):
        """Long messages are sent without truncation (no web URL fallback)."""
        state: AgentState = {
            "messages": [],
            "thread_id": "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58",
        }

        long_message = "A " * 200  # 400 chars

        mock_result = MagicMock(success=True, batch_id="batch-2")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with (
            patch("server.sms_service.SmsService", return_value=mock_service),
            patch("data.thread_repository.ThreadRepository") as mock_repo,
        ):
            mock_repo.return_value.get_sms_external_id.return_value = "+15551234567"
            send_sms_response(state, long_message)

        mock_service.send_sms.assert_called_once()

    def test_no_send_without_thread_id(self):
        """No SMS is sent if thread_id is missing."""
        state: AgentState = {"messages": []}

        with patch("server.sms_service.SmsService") as mock_service_cls:
            send_sms_response(state, "Hello!")

        mock_service_cls.assert_not_called()
