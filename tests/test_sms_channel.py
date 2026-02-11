"""Tests for SMS channel dispatch."""

from unittest.mock import MagicMock, patch

from agent.agent_state import AgentState
from agent.channels.sms_channel import (
    _extract_phone_from_thread_id,
    _strip_markdown,
    send_sms_response,
)


class TestStripMarkdown:
    def test_removes_headers(self):
        assert _strip_markdown("## Hello World") == "Hello World"

    def test_removes_bold(self):
        assert _strip_markdown("This is **bold** text") == "This is bold text"

    def test_removes_italic(self):
        assert _strip_markdown("This is *italic* text") == "This is italic text"

    def test_removes_links(self):
        assert _strip_markdown("[click here](https://example.com)") == "click here"

    def test_removes_code_blocks(self):
        text = "Before\n```python\ncode here\n```\nAfter"
        result = _strip_markdown(text)
        assert "code here" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_inline_code(self):
        assert _strip_markdown("Use `command` now") == "Use command now"

    def test_preserves_plain_text(self):
        assert _strip_markdown("Just plain text") == "Just plain text"


class TestExtractPhoneFromThreadId:
    def test_extracts_phone(self):
        assert _extract_phone_from_thread_id("sms:+15551234567:abc123") == "+15551234567"

    def test_returns_none_for_email_thread(self):
        assert _extract_phone_from_thread_id("user@test.com:abc123") is None

    def test_returns_none_for_non_sms_prefix(self):
        assert _extract_phone_from_thread_id("web:abc123") is None


class TestSendSmsResponse:
    def test_sends_sms_for_short_message(self):
        """Short plain message is sent as-is."""
        state: AgentState = {
            "messages": [],
            "thread_id": "sms:+15551234567:abc123",
            "has_rich_content": False,
        }

        mock_result = MagicMock(success=True, batch_id="batch-1")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        with (
            patch("server.sms_service.SmsService", return_value=mock_service),
            patch("data.sms_thread_repository.SmsThreadRepository") as mock_repo,
        ):
            mock_repo.return_value.update_sms_thread_activity = MagicMock()
            send_sms_response(state, "Hello from Gordie!")

        mock_service.send_sms.assert_called_once()
        call_args = mock_service.send_sms.call_args
        assert call_args[0][0] == "+15551234567"
        assert call_args[0][1] == "Hello from Gordie!"

    def test_truncates_long_message_with_web_url(self):
        """Long messages are truncated and a web URL is appended."""
        state: AgentState = {
            "messages": [],
            "thread_id": "sms:+15551234567:abc123",
            "has_rich_content": False,
        }

        long_message = "A " * 200  # 400 chars

        mock_result = MagicMock(success=True, batch_id="batch-2")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        mock_web_thread = ("web-uuid-123", "sms:+15551234567:abc123")

        with (
            patch("server.sms_service.SmsService", return_value=mock_service),
            patch("data.sms_thread_repository.SmsThreadRepository") as mock_repo,
            patch("data.web_thread_repository.WebThreadRepository") as mock_web_repo,
        ):
            mock_repo.return_value.update_sms_thread_activity = MagicMock()
            mock_web_repo.return_value.get_web_thread_by_thread_id.return_value = mock_web_thread
            send_sms_response(state, long_message)

        sent_text = mock_service.send_sms.call_args[0][1]
        assert "Full response:" in sent_text
        assert "/r/web-uuid-123" in sent_text

    def test_rich_content_appends_web_url(self):
        """Messages with has_rich_content get web URL even if short."""
        state: AgentState = {
            "messages": [],
            "thread_id": "sms:+15551234567:abc123",
            "has_rich_content": True,
        }

        mock_result = MagicMock(success=True, batch_id="batch-3")
        mock_service = MagicMock()
        mock_service.send_sms.return_value = mock_result

        mock_web_thread = ("web-uuid-456", "sms:+15551234567:abc123")

        with (
            patch("server.sms_service.SmsService", return_value=mock_service),
            patch("data.sms_thread_repository.SmsThreadRepository") as mock_repo,
            patch("data.web_thread_repository.WebThreadRepository") as mock_web_repo,
        ):
            mock_repo.return_value.update_sms_thread_activity = MagicMock()
            mock_web_repo.return_value.get_web_thread_by_thread_id.return_value = mock_web_thread
            send_sms_response(state, "Short but rich")

        sent_text = mock_service.send_sms.call_args[0][1]
        assert "Full response:" in sent_text

    def test_no_send_without_thread_id(self):
        """No SMS is sent if thread_id is missing."""
        state: AgentState = {"messages": []}

        with patch("server.sms_service.SmsService") as mock_service_cls:
            send_sms_response(state, "Hello!")

        mock_service_cls.assert_not_called()
