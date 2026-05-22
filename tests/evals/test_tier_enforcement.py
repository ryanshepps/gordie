"""Tests for hosted billing enforcement."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from billing.tier import (
    _tier_cache,
    build_billing_context,
    build_upgrade_message,
    check_league_limit,
    check_question_allowed,
    check_usage_allowed,
    classify_message_intent,
    get_billing_status,
    get_user_tier,
)


@pytest.fixture(autouse=True)
def clear_tier_cache() -> Iterator[None]:
    _tier_cache.clear()
    yield
    _tier_cache.clear()


def _mock_subscription(
    tier: str = "free",
    status: str = "active",
    creem_customer_id: str | None = None,
    current_period_ends_at: datetime | None = None,
) -> tuple[str, str | None, str | None, str, str, datetime | None, datetime]:
    return (
        "user@test.com",
        creem_customer_id,
        "sub_123" if creem_customer_id else None,
        tier,
        status,
        current_period_ends_at,
        datetime.now(UTC),
    )


class TestGetUserTier:
    @patch("billing.tier.SubscriptionRepository")
    def test_no_subscription_returns_free(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription.return_value = None
        assert get_user_tier("nobody@test.com") == "free"

    @patch("billing.tier.SubscriptionRepository")
    def test_active_hosted_returns_hosted(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted", status="active"
        )
        assert get_user_tier("user@test.com") == "hosted"

    @patch("billing.tier.SubscriptionRepository")
    def test_canceled_with_future_period_keeps_hosted(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted",
            status="canceled",
            current_period_ends_at=datetime.now(UTC) + timedelta(days=15),
        )
        assert get_user_tier("user@test.com") == "hosted"

    @patch("billing.tier.SubscriptionRepository")
    def test_canceled_with_past_period_returns_free(self, mock_repo_cls) -> None:
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted",
            status="canceled",
            current_period_ends_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert get_user_tier("user@test.com") == "free"


class TestCheckQuestionAllowed:
    @patch("billing.tier.classify_message_intent")
    @patch("billing.tier.SubscriptionRepository")
    def test_hosted_user_skips_classification(self, mock_sub_cls, mock_classify) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted", status="active"
        )
        allowed, reason = check_question_allowed("paid@test.com", "Who should I start?")

        assert allowed is True
        assert reason == ""
        mock_classify.assert_not_called()

    @patch("billing.tier.classify_message_intent", return_value="general")
    @patch("billing.tier.SubscriptionRepository")
    def test_free_user_general_message_allowed(self, mock_sub_cls, _mock_classify) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription()
        allowed, reason = check_question_allowed("free@test.com", "How do I upgrade?")

        assert allowed is True
        assert reason == ""

    @patch("billing.tier.classify_message_intent", return_value="analysis")
    @patch("billing.tier.SubscriptionRepository")
    def test_free_user_analysis_message_blocked(self, mock_sub_cls, _mock_classify) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription()

        allowed, reason = check_question_allowed("free@test.com", "Should I start McDavid?")

        assert allowed is False
        assert "digest updates for one team" in reason
        assert "$10/mo" in reason
        assert "three teams" in reason

    @patch("billing.tier.make_llm")
    def test_classification_failure_defaults_to_analysis(self, mock_make_llm) -> None:
        mock_make_llm.return_value.invoke.side_effect = RuntimeError("API down")

        assert classify_message_intent("start or sit?") == "analysis"


class TestCheckUsageAllowed:
    @patch("billing.tier.SubscriptionRepository")
    @pytest.mark.parametrize("tier", ["free", "hosted"])
    def test_digest_allowed_for_current_tiers(self, mock_repo_cls, tier: str) -> None:
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier=tier, status="active"
        )
        allowed, reason = check_usage_allowed("user@test.com", "digest")
        assert allowed is True
        assert reason == ""


class TestBuildUpgradeMessage:
    @patch("billing.creem_client.create_checkout_session")
    def test_email_includes_hosted_link(self, mock_checkout) -> None:
        mock_checkout.return_value = "https://checkout.creem.io/hosted"
        result = build_upgrade_message("user@test.com", "Limit reached.", "email")

        assert "Hosted" in result
        assert "$10/mo" in result
        assert "https://checkout.creem.io/hosted" in result
        mock_checkout.assert_called_once_with("hosted_monthly", "user@test.com")

    @patch("billing.creem_client.create_checkout_session")
    def test_sms_includes_hosted_link(self, mock_checkout) -> None:
        mock_checkout.return_value = "https://checkout.creem.io/hosted"
        result = build_upgrade_message("user@test.com", "Limit reached.", "sms")

        assert "https://checkout.creem.io/hosted" in result

    @patch("billing.creem_client.create_checkout_session", side_effect=RuntimeError("API error"))
    def test_fallback_to_reason_on_api_failure(self, _mock_checkout) -> None:
        result = build_upgrade_message("user@test.com", "Limit reached.", "email")
        assert result == "Limit reached."


class TestGetBillingStatus:
    @patch("billing.tier.YahooUserTeamRepository")
    @patch("billing.tier.SubscriptionRepository")
    def test_free_user_status(self, mock_sub_cls, mock_team_cls) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription()
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",)]

        result = get_billing_status("user@test.com")

        assert result["tier"] == "free"
        assert result["status"] == "active"
        assert result["questions_allowed"] is False
        assert result["leagues_connected"] == 1
        assert result["leagues_allowed"] == 1
        assert result["current_period_ends"] is None

    @patch("billing.tier.YahooUserTeamRepository")
    @patch("billing.tier.SubscriptionRepository")
    def test_hosted_user_status(self, mock_sub_cls, mock_team_cls) -> None:
        period_end = datetime(2026, 4, 15, tzinfo=UTC)
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted",
            status="active",
            creem_customer_id="cus_123",
            current_period_ends_at=period_end,
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",)]

        result = get_billing_status("user@test.com")

        assert result["tier"] == "hosted"
        assert result["questions_allowed"] is True
        assert result["current_period_ends"] == "2026-04-15"
        assert result["leagues_connected"] == 2
        assert result["leagues_allowed"] == 3


class TestCheckLeagueLimit:
    @patch("billing.tier.YahooUserTeamRepository")
    @patch("billing.tier.SubscriptionRepository")
    def test_free_user_at_limit_blocked(self, mock_sub_cls, mock_team_cls) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription()
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",)]

        allowed, reason = check_league_limit("free@test.com")

        assert allowed is False
        assert "maxed out at 1 team" in reason
        assert "$10/mo" in reason

    @patch("billing.tier.YahooUserTeamRepository")
    @patch("billing.tier.SubscriptionRepository")
    def test_hosted_user_under_limit_allowed(self, mock_sub_cls, mock_team_cls) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted", status="active"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",)]

        allowed, reason = check_league_limit("hosted@test.com")

        assert allowed is True
        assert reason == ""

    @patch("billing.tier.YahooUserTeamRepository")
    @patch("billing.tier.SubscriptionRepository")
    def test_hosted_user_at_limit_blocked(self, mock_sub_cls, mock_team_cls) -> None:
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="hosted", status="active"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",), ("l3",)]

        allowed, reason = check_league_limit("hosted@test.com")

        assert allowed is False
        assert "maxed out at 3 teams" in reason


class TestBuildBillingContext:
    @patch("billing.creem_client.create_checkout_session")
    def test_email_includes_hosted_link(self, mock_checkout) -> None:
        mock_checkout.return_value = "https://checkout.creem.io/hosted"
        result = build_billing_context("user@test.com", "Limit reached.", "email")

        assert "BILLING LIMIT REACHED" in result
        assert "Limit reached." in result
        assert "https://checkout.creem.io/hosted" in result
        assert "Hosted" in result
        mock_checkout.assert_called_once_with("hosted_monthly", "user@test.com")

    @patch("billing.creem_client.create_checkout_session", side_effect=RuntimeError("API error"))
    def test_fallback_on_api_failure_still_has_context(self, _mock_checkout) -> None:
        result = build_billing_context("user@test.com", "Limit reached.", "email")

        assert "BILLING LIMIT REACHED" in result
        assert "Limit reached." in result
        assert "https://" not in result
