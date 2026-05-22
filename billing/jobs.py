"""Scheduled billing jobs."""

from billing.errors import BillingError
from module.logger import get_logger

logger = get_logger(__name__)


def expire_trials_and_notify() -> None:
    from billing.creem_client import create_checkout_session
    from billing.repository import SubscriptionRepository, UsageTrackingRepository
    from data.yahoo_user_team_repository import YahooUserTeamRepository
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

    def _process_user(user_email: str) -> None:
        usage_repo = UsageTrackingRepository()
        team_repo = YahooUserTeamRepository()
        user_sub_repo = SubscriptionRepository()
        try:
            total_questions = usage_repo.get_total_questions(user_email)
            leagues_connected = len(team_repo.get_user_teams(user_email))
            digests_received = user_sub_repo.get_digest_count(user_email)

            usage = TrialUsageSummary(
                questions_asked=total_questions,
                digests_received=digests_received,
                leagues_connected=leagues_connected,
            )

            standard_url = create_checkout_session("standard_monthly", user_email)

            result = email_service.send_trial_expiration_email(
                to_email=user_email,
                usage=usage,
                standard_checkout_url=standard_url,
            )

            if result.success:
                logger.info(f"Sent trial expiration email to {user_email}")
            else:
                logger.error(
                    f"Failed to send trial expiration email to {user_email}: {result.error}"
                )
        except Exception as exc:
            raise BillingError(f"Trial expiration failed for {user_email}") from exc
        finally:
            usage_repo.close()
            team_repo.close()
            user_sub_repo.close()

    for user_email in expired_emails:
        try:
            _process_user(user_email)
        except BillingError as exc:
            logger.error(str(exc))
