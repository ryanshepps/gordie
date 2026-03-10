import re
from unittest.mock import MagicMock, patch

from server.thread_manager import resolve_sms_thread

PHONE = "+15551234567"
SMS_THREAD_PATTERN = re.compile(r"^sms:\+15551234567:[0-9a-f]{12}$")


@patch("server.thread_manager.SmsThreadRepository")
def test_first_time_phone_creates_new_thread(mock_repo_cls):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.get_latest_thread_for_phone.return_value = None

    result = resolve_sms_thread(PHONE)

    assert result.is_new_thread is True
    assert SMS_THREAD_PATTERN.match(result.thread_id)
    repo.create_sms_thread.assert_called_once()
    repo.update_sms_thread_activity.assert_not_called()


@patch("server.thread_manager.SmsThreadRepository")
def test_returning_phone_reuses_existing_thread(mock_repo_cls):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    existing_thread_id = f"sms:{PHONE}:abc123def456"
    repo.get_latest_thread_for_phone.return_value = (
        existing_thread_id,
        PHONE,
        MagicMock(),
        MagicMock(),
    )

    result = resolve_sms_thread(PHONE)

    assert result.is_new_thread is False
    assert result.thread_id == existing_thread_id
    repo.update_sms_thread_activity.assert_called_once_with(existing_thread_id)
    repo.create_sms_thread.assert_not_called()
