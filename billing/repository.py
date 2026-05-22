"""Repository for user subscriptions."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repository import DatabaseRow, Repository


class SubscriptionRepository(Repository):
    """Repository for managing user subscription records."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("user_subscriptions", session)

    def create_free_subscription(self, user_email: str) -> None:
        self.upsert(
            ["user_email"],
            user_email=user_email,
            tier="free",
            status="active",
        )

    def get_subscription(self, user_email: str) -> DatabaseRow | None:
        return self.get_by(user_email=user_email)

    def activate_subscription(
        self,
        user_email: str,
        creem_customer_id: str,
        creem_subscription_id: str,
        tier: str,
        current_period_ends_at: str,
    ) -> None:
        self.upsert(
            ["user_email"],
            user_email=user_email,
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
            {"user_email": user_email},
            status="active",
            current_period_ends_at=current_period_ends_at,
        )

    def cancel_subscription(self, user_email: str) -> None:
        self.update({"user_email": user_email}, status="canceled")

    def expire_subscription(self, user_email: str) -> None:
        self.update({"user_email": user_email}, tier="free", status="expired")

    def pause_subscription(self, user_email: str) -> None:
        self.update({"user_email": user_email}, status="paused")

    def increment_digest_count(self, user_email: str) -> None:
        self.session.execute(
            text(
                "UPDATE user_subscriptions "
                "SET digest_count = digest_count + 1 "
                "WHERE user_email = :user_email"
            ),
            {"user_email": user_email},
        )
        self.session.commit()

    def get_digest_count(self, user_email: str) -> int:
        result = self.session.execute(
            text("SELECT digest_count FROM user_subscriptions WHERE user_email = :user_email"),
            {"user_email": user_email},
        ).fetchone()
        return int(result[0]) if result else 0

    def find_subscription_by_creem_id(self, creem_subscription_id: str) -> DatabaseRow | None:
        return self.get_by(creem_subscription_id=creem_subscription_id)
