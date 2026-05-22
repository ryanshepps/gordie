"""Tier enforcement for billing limits."""

import time
from datetime import UTC, datetime
from typing import Literal, TypedDict

from billing.repository import SubscriptionRepository
from data.repository import DatabaseRow
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

HOSTED_TIER = "hosted"
HOSTED_PLAN_LABEL = "Hosted"
HOSTED_PLAN_PRICE = "$10/mo"

LEAGUE_LIMITS: dict[str, int | None] = {
    "free": 1,
    HOSTED_TIER: 3,
}

DIGEST_ALLOWED_TIERS = frozenset({"free", HOSTED_TIER})

_tier_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 60


class BillingStatus(TypedDict):
    tier: str
    status: str
    current_period_ends: str | None
    questions_allowed: bool
    leagues_connected: int
    leagues_allowed: int | None


def _resolve_billing_state(sub: DatabaseRow | None) -> tuple[str, str]:
    if not sub:
        return ("free", "expired")

    tier: str = sub[3]
    status: str = sub[4]
    current_period_ends_at: datetime | None = sub[5]

    now = datetime.now(UTC)

    if status == "expired":
        return ("free", "expired")

    if status == "canceled" and current_period_ends_at and current_period_ends_at < now:
        return ("free", status)

    if tier == HOSTED_TIER:
        return (tier, status)

    return ("free", status)


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
    team_repo = YahooUserTeamRepository()
    try:
        sub = sub_repo.get_subscription(email)
        tier, status = _resolve_billing_state(sub)

        current_period_ends_at: datetime | None = sub[5] if sub else None

        leagues_connected = len(team_repo.get_user_teams(email))

        period_end: str | None = None
        if current_period_ends_at and tier == HOSTED_TIER:
            period_end = current_period_ends_at.strftime("%Y-%m-%d")

        return BillingStatus(
            tier=tier,
            status=status,
            current_period_ends=period_end,
            questions_allowed=tier == HOSTED_TIER,
            leagues_connected=leagues_connected,
            leagues_allowed=LEAGUE_LIMITS.get(tier),
        )
    finally:
        sub_repo.close()
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

    if tier == HOSTED_TIER:
        return (True, "")

    intent = classify_message_intent(message)
    if intent == "general":
        return (True, "")

    return (
        False,
        "Free hosted accounts include digest updates for one team. "
        f"Upgrade to {HOSTED_PLAN_LABEL} for {HOSTED_PLAN_PRICE} to ask Gordie questions "
        "and connect up to three teams.",
    )


def check_usage_allowed(email: str, action: str) -> tuple[bool, str]:
    tier = get_user_tier(email)

    if action == "digest":
        if tier in DIGEST_ALLOWED_TIERS:
            return (True, "")
        return (False, "Digest updates are available for free accounts and hosted subscribers.")

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
            f"You're maxed out at {limit} team{'s' if limit > 1 else ''}. "
            f"Upgrade to {HOSTED_PLAN_LABEL} for {HOSTED_PLAN_PRICE} to connect up to three teams.",
        )

    return (True, "")


def build_billing_context(email: str, reason: str, channel: str) -> str:
    try:
        from billing.creem_client import create_checkout_session

        hosted_url = create_checkout_session("hosted_monthly", email)
    except Exception as e:
        logger.warning(f"Failed to generate checkout links for {email}: {e}")
        hosted_url = None

    lines = [
        "BILLING LIMIT REACHED — The user needs the hosted plan to ask Gordie questions.",
        f"Reason: {reason}",
        "",
        "Respond to the user in your normal voice. Acknowledge their question,",
        "explain that free hosted accounts get digest updates for one team,",
        "and offer the hosted upgrade for questions and up to three teams.",
    ]

    if hosted_url:
        lines.append(
            f"\n{HOSTED_PLAN_LABEL} ({HOSTED_PLAN_PRICE}) — 3 teams and questions: {hosted_url}"
        )

    return "\n".join(lines)


def build_upgrade_message(email: str, reason: str, channel: str) -> str:
    try:
        from billing.creem_client import create_checkout_session

        hosted_url = create_checkout_session("hosted_monthly", email)

        if channel == "sms":
            return f"{reason}\n\nHere's the link to upgrade: {hosted_url}"

        return (
            f"{reason}\n\n"
            f"{HOSTED_PLAN_LABEL} ({HOSTED_PLAN_PRICE}) — 3 teams and Gordie questions: {hosted_url}"
        )
    except Exception as e:
        logger.warning(f"Failed to generate checkout links for {email}: {e}")
        return reason
