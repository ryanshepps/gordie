"""Job registration for APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from module.logger import get_logger

logger = get_logger(__name__)


def register_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Register all scheduled notification jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
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
