"""Repository class for user records."""

from typing import Any

from sqlalchemy.orm import Session

from data.repository import Repository


class UserRepository(Repository):
    """Repository for managing user records."""

    def __init__(self, session: Session | None = None):
        """Initialize user repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("users", session)

    def add_user(self, email: str) -> None:
        """Add a new user.

        Args:
            email: User's email address
        """
        self.insert(email=email)

    def get_user(self, email: str) -> tuple[Any, ...] | None:
        """Get a user by email.

        Args:
            email: User's email address

        Returns:
            User record or None if not found
        """
        return self.get_by(email=email)
