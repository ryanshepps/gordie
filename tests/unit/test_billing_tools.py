"""Tests for billing agent tools."""

import json
from unittest.mock import patch

from requests.exceptions import RequestException

from billing.tier import BillingStatus


def _billing_status(
    tier: str = "free",
    status: str = "active",
    current_period_ends: str | None = None,
    questions_allowed: bool = False,
    leagues_connected: int = 0,
    leagues_allowed: int | None = 1,
) -> BillingStatus:
    return BillingStatus(
        tier=tier,
        status=status,
        current_period_ends=current_period_ends,
        questions_allowed=questions_allowed,
        leagues_connected=leagues_connected,
        leagues_allowed=leagues_allowed,
    )


USER_STATE = {"state": {"user_id": "00000000-0000-0000-0000-000000000001"}}


class TestGetSubscriptionStatus:
    @patch("billing.tools.get_subscription_status.get_billing_status_by_user_id")
    def test_free_user_includes_current_limits(self, mock_billing) -> None:
        mock_billing.return_value = _billing_status(leagues_connected=1)

        from billing.tools.get_subscription_status import get_subscription_status

        result = json.loads(
            get_subscription_status.func(state=USER_STATE["state"])  # pyright: ignore[reportAttributeAccessIssue]
        )

        assert result["tier"] == "free"
        assert result["questions_allowed"] is False
        assert result["leagues_allowed"] == 1
        assert "plans" in result
        assert result["plans"]["hosted"]["price"] == "$10/mo"
        assert result["plans"]["free"]["digests"] == "Yes"

    @patch("billing.tools.get_subscription_status.get_billing_status_by_user_id")
    def test_hosted_user_includes_period_end(self, mock_billing) -> None:
        mock_billing.return_value = _billing_status(
            tier="hosted",
            status="active",
            current_period_ends="2026-04-15",
            questions_allowed=True,
            leagues_connected=2,
            leagues_allowed=3,
        )

        from billing.tools.get_subscription_status import get_subscription_status

        result = json.loads(
            get_subscription_status.func(state=USER_STATE["state"])  # pyright: ignore[reportAttributeAccessIssue]
        )

        assert result["questions_allowed"] is True
        assert result["current_period_ends"] == "2026-04-15"


class TestGenerateCheckoutLink:
    @patch("billing.tools.generate_checkout_link._email_for_user_id", return_value="user@test.com")
    @patch("billing.tools.generate_checkout_link.create_checkout_session")
    def test_valid_plan_returns_url(self, mock_checkout, _mock_email) -> None:
        mock_checkout.return_value = "https://checkout.creem.io/sess_abc"

        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            "hosted_monthly", state=USER_STATE["state"]
        )

        assert "https://checkout.creem.io/sess_abc" in result
        assert "$10/mo" in result
        mock_checkout.assert_called_once_with("hosted_monthly", "user@test.com")

    def test_invalid_plan_returns_error(self) -> None:
        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.invoke({**USER_STATE, "plan": "platinum"})

        assert "Invalid plan" in result

    def test_allstar_plan_is_not_valid(self) -> None:
        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            "allstar_monthly", state=USER_STATE["state"]
        )

        assert "Invalid plan" in result
        assert "allstar" not in result.lower()

    @patch("billing.tools.generate_checkout_link._email_for_user_id", return_value="user@test.com")
    @patch(
        "billing.tools.generate_checkout_link.create_checkout_session",
        side_effect=RequestException("API error"),
    )
    def test_api_failure_returns_friendly_error(self, mock_checkout, _mock_email) -> None:
        from billing.tools.generate_checkout_link import generate_checkout_link

        result = generate_checkout_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            "hosted_monthly", state=USER_STATE["state"]
        )

        assert "couldn't generate" in result


class TestGeneratePortalLink:
    @patch("billing.tools.generate_portal_link.get_billing_portal_link")
    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_existing_customer_returns_portal_url(self, mock_repo_cls, mock_portal) -> None:
        mock_repo_cls.return_value.get_subscription_by_user_id.return_value = (
            "00000000-0000-0000-0000-000000000001",
            "cus_789",
            "sub_123",
            "hosted",
            "active",
            None,
            None,
        )
        mock_portal.return_value = "https://billing.creem.io/portal_abc"

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            state=USER_STATE["state"]
        )

        assert "https://billing.creem.io/portal_abc" in result
        mock_portal.assert_called_once_with("cus_789")

    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_no_subscription_returns_error(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription_by_user_id.return_value = None

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            state=USER_STATE["state"]
        )

        assert "No active subscription" in result

    @patch("billing.tools.generate_portal_link.SubscriptionRepository")
    def test_no_creem_customer_id_returns_error(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription_by_user_id.return_value = (
            "00000000-0000-0000-0000-000000000001",
            None,
            None,
            "free",
            "active",
            None,
        )

        from billing.tools.generate_portal_link import generate_portal_link

        result = generate_portal_link.func(  # pyright: ignore[reportAttributeAccessIssue]
            state=USER_STATE["state"]
        )

        assert "No active subscription" in result
