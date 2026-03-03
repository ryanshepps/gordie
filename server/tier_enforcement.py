"""Tier enforcement for billing limits."""

import time
from datetime import UTC, date, datetime, timedelta

from data.subscription_repository import SubscriptionRepository, UsageTrackingRepository
from module.logger import get_logger

logger = get_logger(__name__)

FREE_QUESTIONS_PER_WEEK = 3

LEAGUE_LIMITS: dict[str, int | None] = {
    "free": 1,
    "trialing": None,
    "standard": 3,
    "allstar": None,
}

DIGEST_ALLOWED_TIERS = frozenset({"trialing", "standard", "allstar"})

_tier_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 60


def _current_week_start() -> date:
    today = datetime.now(UTC).date()
    return today - timedelta(days=today.weekday())


def _fetch_tier_from_db(email: str) -> str:
    repo = SubscriptionRepository()
    try:
        sub = repo.get_subscription(email)
        if not sub:
            return "free"

        tier: str = sub[3]
        status: str = sub[4]
        trial_ends_at: datetime | None = sub[5]
        current_period_ends_at: datetime | None = sub[6]

        now = datetime.now(UTC)

        if status == "expired":
            return "free"

        if tier == "trialing" and trial_ends_at and trial_ends_at < now:
            return "free"

        if status == "canceled" and current_period_ends_at and current_period_ends_at < now:
            return "free"

        return tier
    finally:
        repo.close()


def get_user_tier(email: str) -> str:
    now = time.time()
    cached = _tier_cache.get(email)
    if cached:
        tier, cached_at = cached
        if now - cached_at < _CACHE_TTL_SECONDS:
            return tier

    tier = _fetch_tier_from_db(email)
    _tier_cache[email] = (tier, now)
    return tier


def check_usage_allowed(email: str, action: str) -> tuple[bool, str]:
    tier = get_user_tier(email)

    if action == "question":
        if tier != "free":
            return (True, "")

        week_start = _current_week_start()
        usage_repo = UsageTrackingRepository()
        try:
            count = usage_repo.get_weekly_usage(email, week_start)
        finally:
            usage_repo.close()

        if count >= FREE_QUESTIONS_PER_WEEK:
            return (
                False,
                f"You've used all {FREE_QUESTIONS_PER_WEEK} free questions this week. "
                "Upgrade to Standard or All-Star for unlimited questions.",
            )

        usage_repo = UsageTrackingRepository()
        try:
            usage_repo.increment_question_count(email, week_start)
        finally:
            usage_repo.close()

        return (True, "")

    if action == "digest":
        if tier in DIGEST_ALLOWED_TIERS:
            return (True, "")
        return (False, "Digests require an active subscription.")

    return (True, "")


def build_upgrade_message(email: str, reason: str, channel: str) -> str:
    try:
        from server.creem_client import create_checkout_session

        standard_url = create_checkout_session("standard_monthly", email)

        if channel == "sms":
            return f"{reason}\n\nUpgrade: {standard_url}"

        allstar_url = create_checkout_session("allstar_monthly", email)
        return (
            f"{reason}\n\n"
            f"Upgrade to Standard ($10/mo): {standard_url}\n"
            f"Upgrade to All-Star ($18/mo): {allstar_url}"
        )
    except Exception as e:
        logger.warning(f"Failed to generate checkout links for {email}: {e}")
        return reason
