"""Tier enforcement for billing limits."""

import time
from datetime import UTC, date, datetime, timedelta
from typing import Literal, TypedDict

from data.repository import DatabaseRow
from data.subscription_repository import SubscriptionRepository, UsageTrackingRepository
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.llm import make_llm
from module.logger import get_logger

logger = get_logger(__name__)

MessageIntent = Literal["analysis", "general"]

_INTENT_SYSTEM_PROMPT = (
    "You classify fantasy sports messages. Respond with exactly one word.\n\n"
    "Respond 'analysis' if the message asks for fantasy sports advice, player stats, "
    "trade evaluation, roster help, waiver/pickup recommendations, matchup questions, "
    "or any team-specific processing.\n\n"
    "Respond 'general' if the message is about billing, subscriptions, upgrading, "
    "what the assistant can do, greetings, how-to questions about Gordie, "
    "or anything not requiring team/player analysis."
)

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


class BillingStatus(TypedDict):
    tier: str
    status: str
    trial_days_remaining: int | None
    current_period_ends: str | None
    questions_used_this_week: int
    questions_remaining: int | None
    leagues_connected: int
    leagues_allowed: int | None


def _current_week_start() -> date:
    today = datetime.now(UTC).date()
    return today - timedelta(days=today.weekday())


def _resolve_billing_state(sub: DatabaseRow | None) -> tuple[str, str]:
    if not sub:
        return ("free", "expired")

    tier: str = sub[3]
    status: str = sub[4]
    trial_ends_at: datetime | None = sub[5]
    current_period_ends_at: datetime | None = sub[6]

    now = datetime.now(UTC)

    if status == "expired":
        return ("free", "expired")

    if tier == "trialing" and trial_ends_at and trial_ends_at < now:
        return ("free", "expired")

    if status == "canceled" and current_period_ends_at and current_period_ends_at < now:
        return ("free", status)

    return (tier, status)


def _fetch_tier_from_db(email: str) -> str:
    repo = SubscriptionRepository()
    try:
        sub = repo.get_subscription(email)
        tier, _ = _resolve_billing_state(sub)
        return tier
    finally:
        repo.close()


def get_billing_status(email: str) -> BillingStatus:
    sub_repo = SubscriptionRepository()
    usage_repo = UsageTrackingRepository()
    team_repo = YahooUserTeamRepository()
    try:
        sub = sub_repo.get_subscription(email)
        tier, status = _resolve_billing_state(sub)

        trial_ends_at: datetime | None = sub[5] if sub else None
        current_period_ends_at: datetime | None = sub[6] if sub else None

        trial_days: int | None = None
        if tier == "trialing" and trial_ends_at:
            trial_days = max((trial_ends_at - datetime.now(UTC)).days, 0)

        week_start = _current_week_start()
        questions_used = usage_repo.get_weekly_usage(email, week_start)

        questions_remaining: int | None = None
        if tier == "free":
            questions_remaining = max(FREE_QUESTIONS_PER_WEEK - questions_used, 0)

        leagues_connected = len(team_repo.get_user_teams(email))

        period_end: str | None = None
        if current_period_ends_at and tier in ("standard", "allstar"):
            period_end = current_period_ends_at.strftime("%Y-%m-%d")

        return BillingStatus(
            tier=tier,
            status=status,
            trial_days_remaining=trial_days,
            current_period_ends=period_end,
            questions_used_this_week=questions_used,
            questions_remaining=questions_remaining,
            leagues_connected=leagues_connected,
            leagues_allowed=LEAGUE_LIMITS.get(tier),
        )
    finally:
        sub_repo.close()
        usage_repo.close()
        team_repo.close()


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


def classify_message_intent(message: str) -> MessageIntent:
    try:
        llm = make_llm(temperature=0)
        response = llm.invoke(
            [
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ]
        )
        raw = str(response.content).strip().lower()
        if raw == "general":
            return "general"
        return "analysis"
    except Exception as e:
        logger.warning(f"Intent classification failed, defaulting to analysis: {e}")
        return "analysis"


def check_question_allowed(email: str, message: str) -> tuple[bool, str]:
    tier = get_user_tier(email)

    if tier != "free":
        return (True, "")

    intent = classify_message_intent(message)
    if intent == "general":
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
            f"Hey, you've burned through your {FREE_QUESTIONS_PER_WEEK} free questions for the week. "
            "I'm still here, but I need you to upgrade to Standard or All-Star to keep the advice coming.",
        )

    usage_repo = UsageTrackingRepository()
    try:
        usage_repo.increment_question_count(email, week_start)
    finally:
        usage_repo.close()

    return (True, "")


def check_usage_allowed(email: str, action: str) -> tuple[bool, str]:
    tier = get_user_tier(email)

    if action == "digest":
        if tier in DIGEST_ALLOWED_TIERS:
            return (True, "")
        return (
            False,
            "Digests are a perk for subscribers — upgrade and I'll send you one every week.",
        )

    return (True, "")


def check_league_limit(email: str) -> tuple[bool, str]:
    tier = get_user_tier(email)
    limit = LEAGUE_LIMITS.get(tier)

    if limit is None:
        return (True, "")

    team_repo = YahooUserTeamRepository()
    try:
        count = len(team_repo.get_user_teams(email))
    finally:
        team_repo.close()

    if count >= limit:
        return (
            False,
            f"You're maxed out at {limit} league{'s' if limit > 1 else ''} "
            f"on the {tier} tier. Upgrade your plan and I'll cover all your leagues.",
        )

    return (True, "")


def build_billing_context(email: str, reason: str, channel: str) -> str:
    try:
        from server.creem_client import create_checkout_session

        standard_url = create_checkout_session("standard_monthly", email)
        allstar_url = create_checkout_session("allstar_monthly", email)
    except Exception as e:
        logger.warning(f"Failed to generate checkout links for {email}: {e}")
        standard_url = None
        allstar_url = None

    lines = [
        "BILLING LIMIT REACHED — The user has hit their free-tier question limit.",
        f"Reason: {reason}",
        "",
        "Respond to the user in your normal voice. Acknowledge their question,",
        "let them know they've used their free questions for the week,",
        "and encourage them to upgrade. Include the checkout links below.",
    ]

    if channel == "sms" and standard_url:
        lines.append(f"\nUpgrade link: {standard_url}")
    elif standard_url and allstar_url:
        lines.append(f"\nStandard ($10/mo) — 3 leagues, weekly digests: {standard_url}")
        lines.append(f"All-Star ($18/mo) — unlimited everything: {allstar_url}")

    return "\n".join(lines)


def build_upgrade_message(email: str, reason: str, channel: str) -> str:
    try:
        from server.creem_client import create_checkout_session

        standard_url = create_checkout_session("standard_monthly", email)

        if channel == "sms":
            return f"{reason}\n\nHere's the link to upgrade: {standard_url}"

        allstar_url = create_checkout_session("allstar_monthly", email)
        return (
            f"{reason}\n\n"
            f"Standard ($10/mo) — 3 leagues, weekly digests: {standard_url}\n"
            f"All-Star ($18/mo) — unlimited everything: {allstar_url}"
        )
    except Exception as e:
        logger.warning(f"Failed to generate checkout links for {email}: {e}")
        return reason
