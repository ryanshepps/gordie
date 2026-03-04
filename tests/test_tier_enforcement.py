"""Tests for tier enforcement module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from server.tier_enforcement import (
    DIGEST_ALLOWED_TIERS,
    FREE_QUESTIONS_PER_WEEK,
    _tier_cache,
    build_upgrade_message,
    check_league_limit,
    check_question_allowed,
    check_usage_allowed,
    classify_message_intent,
    get_billing_status,
    get_user_tier,
)


@pytest.fixture(autouse=True)
def clear_tier_cache():
    _tier_cache.clear()
    yield
    _tier_cache.clear()


def _mock_subscription(
    tier: str = "free",
    status: str = "expired",
    creem_customer_id: str | None = None,
    trial_ends_at: datetime | None = None,
    current_period_ends_at: datetime | None = None,
) -> tuple[str, str | None, str | None, str, str, datetime | None, datetime | None, datetime]:
    return (
        "user@test.com",
        creem_customer_id,
        "sub_123" if creem_customer_id else None,
        tier,
        status,
        trial_ends_at,
        current_period_ends_at,
        datetime.now(UTC),
    )


class TestGetUserTier:
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_no_subscription_returns_free(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = None
        assert get_user_tier("nobody@test.com") == "free"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_active_standard_returns_standard(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard", status="active"
        )
        assert get_user_tier("user@test.com") == "standard"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_active_allstar_returns_allstar(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="allstar", status="active"
        )
        assert get_user_tier("user@test.com") == "allstar"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_trialing_with_future_end_returns_trialing(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="trialing",
            status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=7),
        )
        assert get_user_tier("user@test.com") == "trialing"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_trialing_with_past_end_returns_free(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="trialing",
            status="trialing",
            trial_ends_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert get_user_tier("user@test.com") == "free"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_expired_status_returns_free(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        assert get_user_tier("user@test.com") == "free"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_canceled_with_future_period_keeps_tier(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard",
            status="canceled",
            current_period_ends_at=datetime.now(UTC) + timedelta(days=15),
        )
        assert get_user_tier("user@test.com") == "standard"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_canceled_with_past_period_returns_free(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard",
            status="canceled",
            current_period_ends_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert get_user_tier("user@test.com") == "free"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_paused_keeps_tier(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="allstar",
            status="paused",
            current_period_ends_at=datetime.now(UTC) + timedelta(days=10),
        )
        assert get_user_tier("user@test.com") == "allstar"



class TestCheckQuestionAllowed:
    @patch("server.tier_enforcement.classify_message_intent")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_paid_user_skips_classification(self, mock_sub_cls, mock_classify):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard", status="active"
        )
        allowed, reason = check_question_allowed("paid@test.com", "Who should I start?")

        assert allowed is True
        assert reason == ""
        mock_classify.assert_not_called()

    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.classify_message_intent", return_value="general")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_general_message_not_counted(
        self, mock_sub_cls, mock_classify, mock_usage_cls
    ):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        allowed, reason = check_question_allowed("free@test.com", "How do I upgrade?")

        assert allowed is True
        assert reason == ""
        mock_usage_cls.return_value.increment_question_count.assert_not_called()

    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.classify_message_intent", return_value="analysis")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_analysis_message_counted(
        self, mock_sub_cls, mock_classify, mock_usage_cls
    ):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = 1

        allowed, reason = check_question_allowed("free@test.com", "Should I start McDavid?")

        assert allowed is True
        assert reason == ""
        mock_usage_cls.return_value.increment_question_count.assert_called_once()

    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.classify_message_intent", return_value="analysis")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_analysis_message_over_quota_blocked(
        self, mock_sub_cls, mock_classify, mock_usage_cls
    ):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = FREE_QUESTIONS_PER_WEEK

        allowed, reason = check_question_allowed("free@test.com", "Trade advice?")

        assert allowed is False
        assert "free questions" in reason
        mock_usage_cls.return_value.increment_question_count.assert_not_called()

    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.classify_message_intent", return_value="general")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_general_message_over_quota_still_allowed(
        self, mock_sub_cls, mock_classify, mock_usage_cls
    ):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        allowed, reason = check_question_allowed("free@test.com", "What can you do?")

        assert allowed is True
        assert reason == ""

    @patch("server.tier_enforcement.ChatOpenAI")
    def test_classification_failure_defaults_to_analysis(self, mock_llm_cls):
        mock_llm_cls.return_value.invoke.side_effect = Exception("API down")

        assert classify_message_intent("start or sit?") == "analysis"


class TestCheckUsageAllowed:
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_digest_allowed_for_paid_tiers(self, mock_repo_cls):
        for tier in DIGEST_ALLOWED_TIERS:
            _tier_cache.clear()
            mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
                tier=tier,
                status="active" if tier != "trialing" else "trialing",
                trial_ends_at=(
                    datetime.now(UTC) + timedelta(days=7) if tier == "trialing" else None
                ),
            )
            allowed, _reason = check_usage_allowed("user@test.com", "digest")
            assert allowed is True, f"Digest should be allowed for {tier}"

    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_digest_blocked_for_free_tier(self, mock_repo_cls):
        mock_repo_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        allowed, reason = check_usage_allowed("free@test.com", "digest")
        assert allowed is False
        assert "subscription" in reason.lower()


class TestBuildUpgradeMessage:
    @patch("server.creem_client.create_checkout_session")
    def test_email_includes_both_plan_links(self, mock_checkout):
        mock_checkout.side_effect = [
            "https://checkout.creem.io/standard",
            "https://checkout.creem.io/allstar",
        ]
        result = build_upgrade_message("user@test.com", "Limit reached.", "email")

        assert "Standard" in result
        assert "All-Star" in result
        assert "https://checkout.creem.io/standard" in result
        assert "https://checkout.creem.io/allstar" in result

    @patch("server.creem_client.create_checkout_session")
    def test_sms_includes_single_link(self, mock_checkout):
        mock_checkout.return_value = "https://checkout.creem.io/standard"
        result = build_upgrade_message("user@test.com", "Limit reached.", "sms")

        assert "https://checkout.creem.io/standard" in result

    @patch("server.creem_client.create_checkout_session", side_effect=Exception("API error"))
    def test_fallback_to_reason_on_api_failure(self, mock_checkout):
        result = build_upgrade_message("user@test.com", "Limit reached.", "email")
        assert result == "Limit reached."


class TestGetBillingStatus:
    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_includes_question_limits(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription()
        mock_usage_cls.return_value.get_weekly_usage.return_value = 2
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",)]

        result = get_billing_status("user@test.com")

        assert result["tier"] == "free"
        assert result["status"] == "expired"
        assert result["questions_used_this_week"] == 2
        assert result["questions_remaining"] == 1
        assert result["leagues_connected"] == 1
        assert result["leagues_allowed"] == 1
        assert result["trial_days_remaining"] is None
        assert result["current_period_ends"] is None

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_trialing_user_includes_trial_days(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        trial_end = datetime.now(UTC) + timedelta(days=5, hours=12)
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="trialing", status="trialing", trial_ends_at=trial_end
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = 0
        mock_team_cls.return_value.get_user_teams.return_value = []

        result = get_billing_status("user@test.com")

        assert result["tier"] == "trialing"
        assert result["trial_days_remaining"] == 5
        assert result["questions_remaining"] is None
        assert result["leagues_allowed"] is None

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_standard_user_includes_period_end(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        period_end = datetime(2026, 4, 15, tzinfo=UTC)
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard",
            status="active",
            creem_customer_id="cus_123",
            current_period_ends_at=period_end,
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = 0
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",)]

        result = get_billing_status("user@test.com")

        assert result["tier"] == "standard"
        assert result["current_period_ends"] == "2026-04-15"
        assert result["leagues_connected"] == 2
        assert result["leagues_allowed"] == 3
        assert result["questions_remaining"] is None

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_no_subscription_defaults_to_free(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = None
        mock_usage_cls.return_value.get_weekly_usage.return_value = 0
        mock_team_cls.return_value.get_user_teams.return_value = []

        result = get_billing_status("nobody@test.com")

        assert result["tier"] == "free"
        assert result["questions_remaining"] == 3

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_expired_trial_resolves_to_free(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="trialing",
            status="trialing",
            trial_ends_at=datetime.now(UTC) - timedelta(days=1),
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = 0
        mock_team_cls.return_value.get_user_teams.return_value = []

        result = get_billing_status("user@test.com")

        assert result["tier"] == "free"
        assert result["status"] == "expired"
        assert result["trial_days_remaining"] is None

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.UsageTrackingRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_allstar_has_unlimited_leagues(self, mock_sub_cls, mock_usage_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="allstar",
            status="active",
            creem_customer_id="cus_456",
            current_period_ends_at=datetime(2026, 5, 1, tzinfo=UTC),
        )
        mock_usage_cls.return_value.get_weekly_usage.return_value = 0
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",), ("l3",), ("l4",)]

        result = get_billing_status("user@test.com")

        assert result["leagues_allowed"] is None
        assert result["leagues_connected"] == 4


class TestCheckLeagueLimit:
    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_with_no_leagues_allowed(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        mock_team_cls.return_value.get_user_teams.return_value = []

        allowed, reason = check_league_limit("free@test.com")

        assert allowed is True
        assert reason == ""

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_free_user_at_limit_blocked(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="free", status="expired"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",)]

        allowed, reason = check_league_limit("free@test.com")

        assert allowed is False
        assert "league limit" in reason
        assert "free" in reason

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_standard_user_under_limit_allowed(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard", status="active"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",)]

        allowed, reason = check_league_limit("standard@test.com")

        assert allowed is True
        assert reason == ""

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_standard_user_at_limit_blocked(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="standard", status="active"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [("l1",), ("l2",), ("l3",)]

        allowed, reason = check_league_limit("standard@test.com")

        assert allowed is False
        assert "league limit" in reason
        assert "standard" in reason

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_allstar_user_unlimited(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="allstar", status="active"
        )
        mock_team_cls.return_value.get_user_teams.return_value = [
            (f"l{i}",) for i in range(10)
        ]

        allowed, reason = check_league_limit("allstar@test.com")

        assert allowed is True
        assert reason == ""

    @patch("server.tier_enforcement.YahooUserTeamRepository")
    @patch("server.tier_enforcement.SubscriptionRepository")
    def test_trialing_user_unlimited(self, mock_sub_cls, mock_team_cls):
        mock_sub_cls.return_value.get_subscription.return_value = _mock_subscription(
            tier="trialing",
            status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=7),
        )
        mock_team_cls.return_value.get_user_teams.return_value = [
            (f"l{i}",) for i in range(5)
        ]

        allowed, reason = check_league_limit("trial@test.com")

        assert allowed is True
        assert reason == ""
