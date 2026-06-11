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


def cleanup_pending_users() -> None:
    """Delete pending_users records older than 7 days."""
    from data.pending_user_repository import PendingUserRepository

    repo = PendingUserRepository()
    try:
        from sqlalchemy import text

        repo.session.execute(
            text(
                "DELETE FROM pending_users WHERE created_at < NOW() - MAKE_INTERVAL(days => :days)"
            ),
            {"days": 7},
        )
        repo.session.commit()
        logger.info("Cleaned up stale pending_users records")
    except Exception as e:
        repo.session.rollback()
        logger.error(f"Failed to clean up pending_users records: {e}")
    finally:
        repo.close()


def cleanup_processed_messages() -> None:
    """Delete processed inbound message records older than 24 hours."""
    from data.processed_inbound_message_repository import ProcessedInboundMessageRepository

    repo = ProcessedInboundMessageRepository()
    try:
        repo.cleanup_expired(max_age_hours=24)
        logger.info("Cleaned up expired processed message records")
    except Exception as e:
        repo.session.rollback()
        logger.error(f"Failed to clean up processed messages: {e}")
    finally:
        repo.close()


def cleanup_expired_temporary_sessions() -> None:
    """Delete expired hosted-trial sessions and anonymous provider tokens."""
    from data.temporary_session_repository import TemporarySessionRepository

    repo = TemporarySessionRepository()
    try:
        deleted_count = repo.cleanup_expired()
        logger.info(f"Cleaned up {deleted_count} expired temporary sessions")
    except Exception as e:
        repo.session.rollback()
        logger.error(f"Failed to clean up temporary sessions: {e}")
    finally:
        repo.close()


def register_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Register all scheduled notification jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    from agent.news.send_news_digest import run_news_digest
    from scheduled.refresh_mlb_stats_db import refresh_mlb_stats_db
    from scheduled.refresh_stats_db import refresh_stats_db
    from scheduled.weekly_digest import run_weekly_digest

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

    scheduler.add_job(
        func=cleanup_pending_users,
        trigger="cron",
        hour=3,
        minute=0,
        id="cleanup_pending_users",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: cleanup_pending_users (daily at 3:00 AM)")

    scheduler.add_job(
        func=cleanup_processed_messages,
        trigger="interval",
        hours=1,
        id="cleanup_processed_messages",
        replace_existing=True,
    )
    logger.info("Registered scheduled job: cleanup_processed_messages (hourly)")

    scheduler.add_job(
        func=cleanup_expired_temporary_sessions,
        trigger="interval",
        hours=1,
        id="cleanup_expired_temporary_sessions",
        replace_existing=True,
    )
    logger.info("Registered scheduled job: cleanup_expired_temporary_sessions (hourly)")
