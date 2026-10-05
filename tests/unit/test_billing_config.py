"""Tests for billing startup validation."""

from unittest.mock import patch

import pytest

from gordie import billing


class TestValidateBillingConfig:
    def test_raises_when_api_key_set_but_webhook_secret_missing(self):
        with (
            patch("gordie.billing._CREEM_API_KEY", "sk_test_key"),
            patch("gordie.billing._CREEM_WEBHOOK_SECRET", ""),
            pytest.raises(RuntimeError, match="CREEM_WEBHOOK_SECRET"),
        ):
            billing.validate_billing_config()

    def test_passes_when_both_keys_present(self):
        with (
            patch("gordie.billing._CREEM_API_KEY", "sk_test_key"),
            patch("gordie.billing._CREEM_WEBHOOK_SECRET", "whsec_test"),
        ):
            billing.validate_billing_config()  # should not raise

    def test_passes_when_no_keys_set(self):
        with (
            patch("gordie.billing._CREEM_API_KEY", ""),
            patch("gordie.billing._CREEM_WEBHOOK_SECRET", ""),
        ):
            billing.validate_billing_config()  # should not raise

    def test_error_message_mentions_both_vars(self):
        with (
            patch("gordie.billing._CREEM_API_KEY", "sk_test_key"),
            patch("gordie.billing._CREEM_WEBHOOK_SECRET", ""),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                billing.validate_billing_config()
            assert "CREEM_API_KEY" in str(exc_info.value)
            assert "CREEM_WEBHOOK_SECRET" in str(exc_info.value)
