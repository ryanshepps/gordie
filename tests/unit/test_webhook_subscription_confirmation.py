"""Tests for subscription confirmation SMS on checkout.completed webhook."""

import logging
from unittest.mock import MagicMock, patch
from uuid import UUID

from billing.webhook import _handle_checkout_completed, _send_subscription_confirmation


class TestSendSubscriptionConfirmation:
    def test_sends_sms_when_user_has_phone(self) -> None:
        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        mock_repo = MagicMock()
        mock_repo.get_by_identity.return_value = (user_id, "created")
        mock_repo.get_identity_external_id.return_value = "+15551234567"

        mock_sms = MagicMock()

        with (
            patch("billing.webhook.UserRepository", return_value=mock_repo),
            patch("billing.webhook.SmsService", return_value=mock_sms),
        ):
            _send_subscription_confirmation("user@test.com", "hosted", logging.getLogger())

        mock_sms.send_sms.assert_called_once()
        phone, message = mock_sms.send_sms.call_args.args
        assert phone == "+15551234567"
        assert "Hosted" in message
        assert "active" in message

    def test_skips_sms_when_user_has_no_phone(self) -> None:
        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        mock_repo = MagicMock()
        mock_repo.get_by_identity.return_value = (user_id, "created")
        mock_repo.get_identity_external_id.return_value = None

        with (
            patch("billing.webhook.UserRepository", return_value=mock_repo),
            patch("billing.webhook.SmsService") as mock_sms_cls,
        ):
            _send_subscription_confirmation("user@test.com", "hosted", logging.getLogger())

        mock_sms_cls.assert_not_called()

    def test_skips_sms_when_user_not_found(self) -> None:
        mock_repo = MagicMock()
        mock_repo.get_by_identity.return_value = None

        with (
            patch("billing.webhook.UserRepository", return_value=mock_repo),
            patch("billing.webhook.SmsService") as mock_sms_cls,
        ):
            _send_subscription_confirmation("unknown@test.com", "hosted", logging.getLogger())

        mock_sms_cls.assert_not_called()

    def test_sms_failure_does_not_raise(self) -> None:
        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        mock_repo = MagicMock()
        mock_repo.get_by_identity.return_value = (user_id, "created")
        mock_repo.get_identity_external_id.return_value = "+15551234567"

        mock_sms = MagicMock()
        mock_sms.send_sms.side_effect = RuntimeError("Sinch down")

        with (
            patch("billing.webhook.UserRepository", return_value=mock_repo),
            patch("billing.webhook.SmsService", return_value=mock_sms),
        ):
            _send_subscription_confirmation("user@test.com", "hosted", logging.getLogger())


class TestCheckoutCompletedTriggersConfirmation:
    def test_sends_confirmation_after_activation(self) -> None:
        obj = {
            "customer": {"id": "cust_123", "email": "user@test.com"},
            "subscription": {"id": "sub_123", "current_period_end_date": "2026-05-01"},
            "product": {"id": "prod_hosted"},
        }
        mock_repo = MagicMock()

        with (
            patch("billing.creem_client.tier_from_product_id", return_value="hosted"),
            patch("billing.webhook._send_subscription_confirmation") as mock_confirm,
        ):
            _handle_checkout_completed(mock_repo, obj, logging.getLogger())

        mock_repo.activate_subscription.assert_called_once()
        mock_confirm.assert_called_once_with("user@test.com", "hosted", logging.getLogger())

    def test_no_confirmation_when_email_missing(self) -> None:
        obj = {
            "customer": {"id": "cust_123"},
            "subscription": {"id": "sub_123"},
            "product": {"id": "prod_hosted"},
        }
        mock_repo = MagicMock()

        with (
            patch("billing.webhook._send_subscription_confirmation") as mock_confirm,
        ):
            _handle_checkout_completed(mock_repo, obj, logging.getLogger())

        mock_repo.activate_subscription.assert_not_called()
        mock_confirm.assert_not_called()
