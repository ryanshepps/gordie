"""Repository for user subscriptions and usage tracking."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import DatabaseRow, Repository
from data.user_repository import UserRepository


class SubscriptionRepository(Repository):
    """Repository for managing user subscription records."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("user_subscriptions", session)

    def _user_id_for_email(self, user_email: str) -> UUID:
        return UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)

    def create_trialing_subscription(self, user_email: str) -> None:
        trial_ends_at = datetime.now(UTC) + timedelta(days=14)
        user_id = self._user_id_for_email(user_email)
        self.upsert(
            ["user_id"],
            user_id=user_id,
            tier="trialing",
            status="trialing",
            trial_ends_at=trial_ends_at.isoformat(),
        )

    def get_subscription(self, user_email: str) -> DatabaseRow | None:
        return self.session.execute(
            text(
                """
                SELECT
                    ui.external_id AS user_email,
                    us.creem_customer_id,
                    us.creem_subscription_id,
                    us.tier,
                    us.status,
                    us.trial_ends_at,
                    us.current_period_ends_at,
                    us.digest_count,
                    us.created_at
                FROM user_subscriptions us
                JOIN user_identities ui
                    ON ui.user_id = us.user_id
                    AND ui.medium = :medium
                WHERE ui.external_id = :user_email
                """
            ),
            {"medium": Medium.EMAIL.value, "user_email": user_email},
        ).fetchone()

    def activate_subscription(
        self,
        user_email: str,
        creem_customer_id: str,
        creem_subscription_id: str,
        tier: str,
        current_period_ends_at: str,
    ) -> None:
        user_id = self._user_id_for_email(user_email)
        self.upsert(
            ["user_id"],
            user_id=user_id,
            creem_customer_id=creem_customer_id,
            creem_subscription_id=creem_subscription_id,
            tier=tier,
            status="active",
            current_period_ends_at=current_period_ends_at,
        )

    def renew_subscription(
        self,
        user_email: str,
        current_period_ends_at: str,
    ) -> None:
        self.update(
            {"user_id": self._user_id_for_email(user_email)},
            status="active",
            current_period_ends_at=current_period_ends_at,
        )

    def cancel_subscription(self, user_email: str) -> None:
        self.update({"user_id": self._user_id_for_email(user_email)}, status="canceled")

    def expire_subscription(self, user_email: str) -> None:
        self.update({"user_id": self._user_id_for_email(user_email)}, tier="free", status="expired")

    def pause_subscription(self, user_email: str) -> None:
        self.update({"user_id": self._user_id_for_email(user_email)}, status="paused")

    def expire_trials(self) -> list[str]:
        now = datetime.now(UTC).isoformat()
        result = self.session.execute(
            text(
                """
                UPDATE user_subscriptions us
                SET tier = 'free', status = 'expired'
                FROM user_identities ui
                WHERE us.user_id = ui.user_id
                    AND ui.medium = :medium
                    AND us.tier = 'trialing'
                    AND us.trial_ends_at < :now
                RETURNING ui.external_id
                """
            ),
            {"medium": Medium.EMAIL.value, "now": now},
        ).fetchall()
        self.session.commit()
        return [row[0] for row in result]

    def increment_digest_count(self, user_email: str) -> None:
        self.session.execute(
            text(
                "UPDATE user_subscriptions "
                "SET digest_count = digest_count + 1 "
                "WHERE user_id = :user_id"
            ),
            {"user_id": self._user_id_for_email(user_email)},
        )
        self.session.commit()

    def get_digest_count(self, user_email: str) -> int:
        result = self.session.execute(
            text("SELECT digest_count FROM user_subscriptions WHERE user_id = :user_id"),
            {"user_id": self._user_id_for_email(user_email)},
        ).fetchone()
        return int(result[0]) if result else 0

    def find_subscription_by_creem_id(self, creem_subscription_id: str) -> DatabaseRow | None:
        return self.session.execute(
            text(
                """
                SELECT
                    ui.external_id AS user_email,
                    us.creem_customer_id,
                    us.creem_subscription_id,
                    us.tier,
                    us.status,
                    us.trial_ends_at,
                    us.current_period_ends_at,
                    us.digest_count,
                    us.created_at
                FROM user_subscriptions us
                JOIN user_identities ui
                    ON ui.user_id = us.user_id
                    AND ui.medium = :medium
                WHERE us.creem_subscription_id = :creem_subscription_id
                """
            ),
            {
                "medium": Medium.EMAIL.value,
                "creem_subscription_id": creem_subscription_id,
            },
        ).fetchone()


class UsageTrackingRepository(Repository):
    """Repository for tracking weekly question usage."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("usage_tracking", session)

    def _user_id_for_email(self, user_email: str) -> UUID:
        return UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)

    def get_weekly_usage(self, user_email: str, week_start: date) -> int:
        result = self.session.execute(
            text(
                "SELECT question_count FROM usage_tracking "
                "WHERE user_id = :user_id AND week_start = :week_start"
            ),
            {"user_id": self._user_id_for_email(user_email), "week_start": week_start.isoformat()},
        ).fetchone()
        if result:
            return int(result[0])
        return 0

    def get_total_questions(self, user_email: str) -> int:
        result = self.session.execute(
            text(
                "SELECT COALESCE(SUM(question_count), 0) FROM usage_tracking "
                "WHERE user_id = :user_id"
            ),
            {"user_id": self._user_id_for_email(user_email)},
        ).fetchone()
        return int(result[0]) if result else 0

    def increment_question_count(self, user_email: str, week_start: date) -> int:
        result = self.session.execute(
            text(
                "INSERT INTO usage_tracking (user_id, week_start, question_count) "
                "VALUES (:user_id, :week_start, 1) "
                "ON CONFLICT (user_id, week_start) "
                "DO UPDATE SET question_count = usage_tracking.question_count + 1 "
                "RETURNING question_count"
            ),
            {"user_id": self._user_id_for_email(user_email), "week_start": week_start.isoformat()},
        ).fetchone()
        self.session.commit()
        return int(result[0]) if result else 1
