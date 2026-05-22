"""Unified job runner for scheduled per-user jobs.

Handles the common pattern of:
1. Fetching opted-in user+league pairs
2. Iterating with traced spans (user.email, league.id)
3. Counting success/failed/skipped results
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from billing.repository import SubscriptionRepository
from data.notification_preference_repository import NotificationPreferenceRepository
from module.logger import get_logger
from module.tracing import create_span

logger = get_logger(__name__)


def _record_digest_delivery(user_email: str) -> None:
    sub_repo = SubscriptionRepository()
    try:
        sub_repo.increment_digest_count(user_email)
    except Exception as e:
        logger.warning(f"Failed to record digest delivery for {user_email}: {e}")
    finally:
        sub_repo.close()


@dataclass
class JobResult:
    success: int = 0
    failed: int = 0
    skipped: int = 0


def is_user_eligible_for_digest(user_email: str) -> bool:
    from billing.tier import DIGEST_ALLOWED_TIERS, get_user_tier

    return get_user_tier(user_email) in DIGEST_ALLOWED_TIERS


def run_per_user_job(
    job_name: str,
    notification_type: str,
    handler: Callable[[str, str], bool],
) -> JobResult:
    """Run a job for each opted-in user+league pair with automatic tracing.

    Each invocation of `handler` is wrapped in a span with `user.email`
    and `league.id` attributes. New jobs only need to provide the handler.

    Args:
        job_name: Name used for logging and the span (e.g. "news_digest")
        notification_type: Preference type to query (e.g. "news_digest", "weekly_digest")
        handler: Function(user_email, league_id) -> bool.
                 Return True if work was done, False to count as skipped.
                 Raise an exception to count as failed.

    Returns:
        JobResult with success/failed/skipped counts
    """
    logger.info(f"Starting {job_name} job")

    repo = NotificationPreferenceRepository()
    try:
        user_leagues = repo.get_all_enabled_for_type(notification_type)
    finally:
        repo.close()

    if not user_leagues:
        logger.info(f"No users opted in for {job_name}")
        return JobResult()

    logger.info(f"Processing {job_name} for {len(user_leagues)} user+league combinations")

    from billing.tier import DIGEST_ALLOWED_TIERS, get_user_tier

    result = JobResult()
    for user_email, league_id in user_leagues:
        tier = get_user_tier(user_email)
        if tier not in DIGEST_ALLOWED_TIERS:
            result.skipped += 1
            continue

        with create_span(
            f"{job_name}.user",
            {"user.email": user_email, "league.id": league_id},
        ):
            try:
                sent = handler(user_email, league_id)
                if sent:
                    result.success += 1
                    _record_digest_delivery(user_email)
                else:
                    result.skipped += 1
            except Exception as e:
                result.failed += 1
                logger.error(f"{job_name} failed for {user_email}/{league_id}: {e}")

    logger.info(
        f"{job_name} complete: {result.success} sent, "
        f"{result.skipped} skipped, {result.failed} failed"
    )
    return result
