"""Repository class for user records."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import DatabaseRow, Repository


class UserRepository(Repository):
    """Repository for managing user records."""

    def __init__(self, session: Session | None = None) -> None:
        """Initialize user repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("users", session)

    def get_by_identity(self, medium: Medium, external_id: str) -> DatabaseRow | None:
        """Get a user by one of its per-medium identities."""
        return self.session.execute(
            text(
                """
                SELECT u.id, u.created_at
                FROM users u
                JOIN user_identities ui ON ui.user_id = u.id
                WHERE ui.medium = :medium AND ui.external_id = :external_id
                """
            ),
            {"medium": medium.value, "external_id": external_id},
        ).fetchone()

    def create_with_identity(
        self,
        medium: Medium,
        external_id: str,
        display_name: str | None = None,
    ) -> UUID:
        """Create a canonical user and its first identity, or return the existing user."""
        try:
            result = self.session.execute(
                text("INSERT INTO users DEFAULT VALUES RETURNING id")
            ).fetchone()
            if result is None:
                raise RuntimeError("Failed to create user")

            user_id = UUID(str(result[0]))
            self._insert_identity(user_id, medium, external_id, display_name)
            self.session.commit()
            return user_id
        except IntegrityError:
            self.session.rollback()

        existing = self.get_by_identity(medium, external_id)
        if existing is None:
            raise RuntimeError("Identity creation conflicted but no existing user was found")
        return UUID(str(existing[0]))

    def resolve_user_id(
        self,
        medium: Medium,
        external_id: str,
        display_name: str | None = None,
    ) -> UUID:
        """Return the canonical user for an identity, creating it when needed."""
        user = self.get_by_identity(medium, external_id)
        if user:
            return UUID(str(user[0]))
        return self.create_with_identity(medium, external_id, display_name)

    def link_identity(
        self,
        user_id: UUID,
        medium: Medium,
        external_id: str,
        display_name: str | None = None,
    ) -> None:
        """Attach a new identity to an existing canonical user."""
        self._insert_identity(user_id, medium, external_id, display_name)
        self.session.commit()

    def merge_users(self, source_user_id: UUID, target_user_id: UUID) -> None:
        """Move identities and threads from a temporary user into the canonical user."""
        self.session.execute(
            text("UPDATE user_identities SET user_id = :target WHERE user_id = :source"),
            {"source": source_user_id, "target": target_user_id},
        )
        self.session.execute(
            text("UPDATE conversation_threads SET user_id = :target WHERE user_id = :source"),
            {"source": source_user_id, "target": target_user_id},
        )
        self.session.execute(
            text("DELETE FROM users WHERE id = :source"),
            {"source": source_user_id},
        )
        self.session.commit()

    def get_identity_external_id(self, user_id: UUID, medium: Medium) -> str | None:
        """Return a user's external ID for the requested medium."""
        result = self.session.execute(
            text(
                """
                SELECT external_id
                FROM user_identities
                WHERE user_id = :user_id AND medium = :medium
                """
            ),
            {"user_id": user_id, "medium": medium.value},
        ).fetchone()
        if not result:
            return None
        return str(result[0])

    def set_sms_opt_out(self, phone_number: str, opted_out: bool) -> None:
        """Set SMS opt-out status for the identity with this phone number."""
        self.session.execute(
            text(
                """
                UPDATE user_identities
                SET opted_out = :opted_out
                WHERE medium = :medium AND external_id = :phone_number
                """
            ),
            {
                "opted_out": opted_out,
                "medium": Medium.SMS.value,
                "phone_number": phone_number,
            },
        )
        self.session.commit()

    def is_sms_opted_out(self, phone_number: str) -> bool:
        """Check whether the SMS identity is opted out."""
        result = self.session.execute(
            text(
                """
                SELECT opted_out
                FROM user_identities
                WHERE medium = :medium AND external_id = :phone_number
                """
            ),
            {"medium": Medium.SMS.value, "phone_number": phone_number},
        ).fetchone()
        if result:
            return bool(result[0])
        return False

    def _insert_identity(
        self,
        user_id: UUID,
        medium: Medium,
        external_id: str,
        display_name: str | None,
    ) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO user_identities (user_id, medium, external_id, display_name)
                VALUES (:user_id, :medium, :external_id, :display_name)
                """
            ),
            {
                "user_id": user_id,
                "medium": medium.value,
                "external_id": external_id,
                "display_name": display_name,
            },
        )
