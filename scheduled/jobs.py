"""Job registration for APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from module.logger import get_logger

logger = get_logger(__name__)


def cleanup_expired_pending_oauth() -> None:
    """Delete pending OAuth records older than 24 hours."""
    from data.pending_oauth_repository import PendingOAuthRepository

    repo = PendingOAuthRepository()
    try:
        repo.cleanup_expired(max_age_hours=24)
        logger.info("Cleaned up expired pending_oauth records")
    except Exception as e:
        logger.error(f"Failed to clean up pending_oauth records: {e}")
    finally:
        repo.close()


def register_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Register all scheduled notification jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    from agent.news.send_news_digest import run_news_digest
    from scheduled.weekly_digest import run_weekly_digest

    scheduler.add_job(
        func=run_weekly_digest,
        trigger="cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id="weekly_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: weekly_digest (Sundays at 8:00 AM)")

    scheduler.add_job(
        func=run_news_digest,
        trigger="cron",
        hour=8,
        minute=0,
        id="news_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: news_digest (Daily at 8:00 AM UTC)")

    scheduler.add_job(
        func=cleanup_expired_pending_oauth,
        trigger="interval",
        hours=1,
        id="cleanup_pending_oauth",
        replace_existing=True,
    )
    logger.info("Registered scheduled job: cleanup_pending_oauth (hourly)")
