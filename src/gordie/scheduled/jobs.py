"""Job registration for APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from gordie.module.logger import get_logger

logger = get_logger(__name__)


def cleanup_expired_pending_oauth() -> None:
    """Delete pending OAuth records older than 24 hours."""
    from gordie.data.pending_oauth_repository import PendingOAuthRepository

    repo = PendingOAuthRepository()
    try:
        repo.cleanup_expired(max_age_hours=24)
        logger.info("Cleaned up expired pending_oauth records")
    except Exception as e:
        logger.error(f"Failed to clean up pending_oauth records: {e}")
    finally:
        repo.close()


def register_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Register scheduled maintenance and stats jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    from gordie.scheduled.refresh_mlb_stats_db import refresh_mlb_stats_db
    from gordie.scheduled.refresh_stats_db import refresh_stats_db

    scheduler.add_job(
        func=refresh_stats_db,
        trigger="cron",
        hour=7,
        minute=0,
        id="refresh_stats_db",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: refresh_stats_db (daily at 7:00 AM UTC)")

    scheduler.add_job(
        func=refresh_mlb_stats_db,
        trigger="cron",
        hour=7,
        minute=30,
        id="refresh_mlb_stats_db",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: refresh_mlb_stats_db (daily at 7:30 AM UTC)")

    scheduler.add_job(
        func=cleanup_expired_pending_oauth,
        trigger="interval",
        hours=1,
        id="cleanup_pending_oauth",
        replace_existing=True,
    )
    logger.info("Registered scheduled job: cleanup_pending_oauth (hourly)")
