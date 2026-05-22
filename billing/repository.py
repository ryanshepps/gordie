"""Repository for user subscriptions."""

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

    def create_free_subscription(self, user_email: str) -> None:
        user_id = self._user_id_for_email(user_email)
        self.upsert(
            ["user_id"],
            user_id=user_id,
            tier="free",
            status="active",
        )

    def _user_id_for_email(self, user_email: str) -> UUID:
        return UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)

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
