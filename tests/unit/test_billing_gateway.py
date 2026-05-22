"""Tests for BillingGateway protocol and NullBillingGateway implementation."""

from billing.gateway import BillingGateway, NullBillingGateway


class TestNullBillingGateway:
    def test_satisfies_billing_gateway_protocol(self):
        gw = NullBillingGateway()
        assert isinstance(gw, BillingGateway)

    def test_check_question_allowed_always_permits(self):
        gw = NullBillingGateway()
        allowed, reason = gw.check_question_allowed("user@test.com", "Who should I start?")
        assert allowed is True
        assert reason == ""

    def test_check_usage_allowed_always_permits_digest(self):
        gw = NullBillingGateway()
        allowed, reason = gw.check_usage_allowed("user@test.com", "digest")
        assert allowed is True
        assert reason == ""

    def test_check_league_limit_always_permits(self):
        gw = NullBillingGateway()
        allowed, reason = gw.check_league_limit("user@test.com")
        assert allowed is True
        assert reason == ""

    def test_get_user_tier_returns_free(self):
        gw = NullBillingGateway()
        assert gw.get_user_tier("user@test.com") == "free"

    def test_build_billing_context_returns_empty(self):
        gw = NullBillingGateway()
        ctx = gw.build_billing_context("user@test.com", "some reason", "email")
        assert ctx == ""

    def test_build_upgrade_message_returns_reason(self):
        gw = NullBillingGateway()
        msg = gw.build_upgrade_message("user@test.com", "You've hit your limit.", "email")
        assert msg == "You've hit your limit."

    def test_check_question_allowed_with_empty_message(self):
        gw = NullBillingGateway()
        allowed, reason = gw.check_question_allowed("user@test.com", "")
        assert allowed is True
        assert reason == ""
