"""Repository class for pending user records (pre-OAuth)."""

import uuid

from sqlalchemy.orm import Session

from data.repository import DatabaseRow, Repository


class PendingUserRepository(Repository):
    """Repository for managing pending user records during SMS onboarding."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("pending_users", session)

    def add_pending_user(
        self,
        phone_number: str | None = None,
        email: str | None = None,
    ) -> str:
        """Create a pending user record.

        Args:
            phone_number: User's phone number (for SMS signups)
            email: User's email (for web signups)

        Returns:
            The generated UUID for the pending user
        """
        pending_id = str(uuid.uuid4())
        self.insert(id=pending_id, phone_number=phone_number, email=email)
        return pending_id

    def get_pending_user_by_phone(self, phone_number: str) -> DatabaseRow | None:
        """Get a pending user by phone number.

        Args:
            phone_number: The phone number to look up

        Returns:
            Record tuple or None if not found
        """
        return self.get_by(phone_number=phone_number)

    def get_pending_user_by_email(self, email: str) -> DatabaseRow | None:
        """Get a pending user by email.

        Args:
            email: The email to look up

        Returns:
            Record tuple or None if not found
        """
        return self.get_by(email=email)

    def delete_pending_user(self, pending_id: str) -> None:
        """Delete a pending user record.

        Args:
            pending_id: The UUID of the pending user record
        """
        self.delete(id=pending_id)
