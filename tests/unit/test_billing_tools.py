"""Tests for billing agent tools."""

import json
from unittest.mock import patch

from billing.tier import BillingStatus


def _billing_status(
    tier: str = "free",
    status: str = "expired",
    trial_days_remaining: int | None = None,
    current_period_ends: str | None = None,
    questions_used_this_week: int = 0,
    questions_remaining: int | None = None,
    leagues_connected: int = 0,
    leagues_allowed: int | None = 1,
) -> BillingStatus:
    return BillingStatus(
        tier=tier,
        status=status,
        trial_days_remaining=trial_days_remaining,
        current_period_ends=current_period_ends,
        questions_used_this_week=questions_used_this_week,
        questions_remaining=questions_remaining,
        leagues_connected=leagues_connected,
        leagues_allowed=leagues_allowed,
    )


class TestGetSubscriptionStatus:
    @patch("billing.tools.get_subscription_status.get_billing_status")
    def test_free_user_includes_question_fields(self, mock_billing):
        mock_billing.return_value = _billing_status(
            questions_used_this_week=2, questions_remaining=1, leagues_connected=1
        )

        from billing.tools.get_subscription_status import get_subscription_status

        result = json.loads(get_subscription_status.invoke({"user_email": "user@test.com"}))

        assert result["tier"] == "free"
        assert result["questions_used_this_week"] == 2
        assert result["questions_remaining"] == 1
        assert "plans" in result
        assert result["plans"]["standard"]["price"] == "$10/mo or $80/yr"

    @patch("billing.tools.get_subscription_status.get_billing_status")
    def test_paid_user_omits_question_fields(self, mock_billing):
        mock_billing.return_value = _billing_status(
            tier="standard",
            status="active",
            current_period_ends="2026-04-15",
            leagues_connected=2,
            leagues_allowed=3,
        )

        from billing.tools.get_subscription_status import get_subscription_status

        result = json.loads(get_subscription_status.invoke({"user_email": "user@test.com"}))

        assert "questions_used_this_week" not in result
        assert result["current_period_ends"] == "2026-04-15"

    @patch("billing.tools.get_subscription_status.get_billing_status")
    def test_unlimited_leagues_serialized_as_string(self, mock_billing):
        mock_billing.return_value = _billing_status(
            tier="allstar", status="active", leagues_allowed=None
        )

        from billing.tools.get_subscription_status import get_subscription_status

        result = json.loads(get_subscription_status.invoke({"user_email": "user@test.com"}))

        assert result["leagues_allowed"] == "unlimited"


class TestGenerateCheckoutLink:
    @patch("billing.tools.generate_checkout_link.create_checkout_session")
    def test_valid_plan_returns_url(self, mock_checkout):
        mock_checkout.return_value = "https://checkout.creem.io/sess_abc"

        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.invoke(
            {"user_email": "user@test.com", "plan": "standard_monthly"}
        )

        assert "https://checkout.creem.io/sess_abc" in result
        assert "$10/mo" in result
        mock_checkout.assert_called_once_with("standard_monthly", "user@test.com")

    @patch("billing.tools.generate_checkout_link.create_checkout_session")
    def test_annual_plan_shows_savings(self, mock_checkout):
        mock_checkout.return_value = "https://checkout.creem.io/sess_def"

        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.invoke(
            {"user_email": "user@test.com", "plan": "standard_annual"}
        )

        assert "save 33%" in result
        assert "$80/yr" in result

    def test_invalid_plan_returns_error(self):
        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.invoke({"user_email": "user@test.com", "plan": "platinum"})

        assert "Invalid plan" in result

    @patch(
        "billing.tools.generate_checkout_link.create_checkout_session",
        side_effect=Exception("API error"),
    )
    def test_api_failure_returns_friendly_error(self, mock_checkout):
        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.invoke(
            {"user_email": "user@test.com", "plan": "allstar_monthly"}
        )

        assert "couldn't generate" in result


class TestGeneratePortalLink:
    @patch("billing.tools.generate_portal_link.get_billing_portal_link")
    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_existing_customer_returns_portal_url(self, mock_repo_cls, mock_portal):
        mock_repo_cls.return_value.get_subscription.return_value = (
            "user@test.com",
            "cus_789",
            "sub_123",
            "standard",
            "active",
            None,
            None,
            None,
        )
        mock_portal.return_value = "https://billing.creem.io/portal_abc"

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.invoke({"user_email": "user@test.com"})

        assert "https://billing.creem.io/portal_abc" in result
        mock_portal.assert_called_once_with("cus_789")

    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_no_subscription_returns_error(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = None

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.invoke({"user_email": "nobody@test.com"})

        assert "No active subscription" in result

    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_no_creem_customer_id_returns_error(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = (
            "user@test.com",
            None,
            None,
            "trialing",
            "trialing",
            None,
            None,
            None,
        )

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.invoke({"user_email": "trial@test.com"})

        assert "No active subscription" in result
