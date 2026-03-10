"""Job registration for APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from module.logger import get_logger

logger = get_logger(__name__)


def expire_trials_and_notify() -> None:
    from data.subscription_repository import SubscriptionRepository, UsageTrackingRepository
    from data.yahoo_user_team_repository import YahooUserTeamRepository
    from server.creem_client import create_checkout_session
    from server.email_service import EmailService, TrialUsageSummary

    sub_repo = SubscriptionRepository()
    try:
        expired_emails = sub_repo.expire_trials()
    finally:
        sub_repo.close()

    if not expired_emails:
        logger.info("No trials to expire")
        return

    logger.info(f"Expired {len(expired_emails)} trials, sending notification emails")

    email_service = EmailService()

    for user_email in expired_emails:
        usage_repo = UsageTrackingRepository()
        team_repo = YahooUserTeamRepository()
        sub_repo = SubscriptionRepository()
        try:
            total_questions = usage_repo.get_total_questions(user_email)
            leagues_connected = len(team_repo.get_user_teams(user_email))
            digests_received = sub_repo.get_digest_count(user_email)

            usage = TrialUsageSummary(
                questions_asked=total_questions,
                digests_received=digests_received,
                leagues_connected=leagues_connected,
            )

            standard_url = create_checkout_session("standard_monthly", user_email)
            allstar_url = create_checkout_session("allstar_monthly", user_email)

            result = email_service.send_trial_expiration_email(
                to_email=user_email,
                usage=usage,
                standard_checkout_url=standard_url,
                allstar_checkout_url=allstar_url,
            )

            if result.success:
                logger.info(f"Sent trial expiration email to {user_email}")
            else:
                logger.error(f"Failed to send trial expiration email to {user_email}: {result.error}")
        except Exception as e:
            logger.error(f"Error processing trial expiration for {user_email}: {e}")
        finally:
            usage_repo.close()
            team_repo.close()
            sub_repo.close()


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
                "DELETE FROM pending_users "
                "WHERE created_at < NOW() - MAKE_INTERVAL(days => :days)"
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
    """Delete processed_sms and processed_emails records older than 24 hours."""
    from sqlalchemy import text

    from data.database import get_session

    session = get_session()
    try:
        for table in ("processed_sms", "processed_emails"):
            session.execute(
                text(
                    f"DELETE FROM {table} WHERE created_at < NOW() - MAKE_INTERVAL(hours => :hours)"
                ),
                {"hours": 24},
            )
        session.commit()
        logger.info("Cleaned up expired processed message records")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to clean up processed messages: {e}")
    finally:
        session.close()


def register_scheduled_jobs(scheduler: BackgroundScheduler) -> None:
    """Register all scheduled notification jobs.

    Args:
        scheduler: APScheduler BackgroundScheduler instance
    """
    from agent.news.send_news_digest import run_news_digest
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
        func=expire_trials_and_notify,
        trigger="cron",
        hour=6,
        minute=0,
        id="expire_trials",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered scheduled job: expire_trials (daily at 6:00 AM UTC)")

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
