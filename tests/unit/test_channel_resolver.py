"""Tests for delivery channel resolution."""

from unittest.mock import MagicMock, patch

from scheduled.channel_resolver import EmailDelivery, SmsDelivery, resolve_delivery_channel


class TestResolveDeliveryChannel:
    @patch("scheduled.channel_resolver.UserRepository")
    def test_sms_when_user_has_phone_and_not_opted_out(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_user.return_value = ("user@test.com", "2024-01-01", "+15551234567", False)
        mock_repo_cls.return_value = mock_repo

        result = resolve_delivery_channel("user@test.com")

        assert isinstance(result, SmsDelivery)
        assert result.phone_number == "+15551234567"

    @patch("scheduled.channel_resolver.UserRepository")
    def test_email_when_user_has_no_phone(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_user.return_value = ("user@test.com", "2024-01-01", None, False)
        mock_repo_cls.return_value = mock_repo

        result = resolve_delivery_channel("user@test.com")

        assert isinstance(result, EmailDelivery)

    @patch("scheduled.channel_resolver.UserRepository")
    def test_email_when_user_opted_out_of_sms(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_user.return_value = ("user@test.com", "2024-01-01", "+15551234567", True)
        mock_repo_cls.return_value = mock_repo

        result = resolve_delivery_channel("user@test.com")

        assert isinstance(result, EmailDelivery)

    @patch("scheduled.channel_resolver.UserRepository")
    def test_email_when_user_not_found(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_user.return_value = None
        mock_repo_cls.return_value = mock_repo

        result = resolve_delivery_channel("unknown@test.com")

        assert isinstance(result, EmailDelivery)
