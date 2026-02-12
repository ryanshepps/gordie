"""Repository class for user records."""

from typing import Any

from sqlalchemy import text
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

    def add_user_with_phone(self, email: str, phone_number: str) -> None:
        """Add a new user with both email and phone number.

        Args:
            email: User's email address
            phone_number: User's phone number (E.164 format)
        """
        self.insert(email=email, phone_number=phone_number)

    def get_user(self, email: str) -> tuple[Any, ...] | None:
        """Get a user by email.

        Args:
            email: User's email address

        Returns:
            User record or None if not found
        """
        return self.get_by(email=email)

    def get_user_by_phone(self, phone_number: str) -> tuple[Any, ...] | None:
        """Get a user by phone number.

        Args:
            phone_number: User's phone number

        Returns:
            User record or None if not found
        """
        return self.get_by(phone_number=phone_number)

    def add_phone_to_user(self, email: str, phone_number: str) -> None:
        """Associate a phone number with an existing user.

        Args:
            email: User's email address
            phone_number: Phone number to add
        """
        self.update({"email": email}, phone_number=phone_number)

    def set_sms_opt_out(self, phone_number: str, opted_out: bool) -> None:
        """Set SMS opt-out status for a user by phone number.

        Args:
            phone_number: User's phone number
            opted_out: Whether the user has opted out of SMS
        """
        self.update({"phone_number": phone_number}, sms_opted_out=opted_out)

    def is_sms_opted_out(self, phone_number: str) -> bool:
        """Check if a user has opted out of SMS.

        Args:
            phone_number: User's phone number

        Returns:
            True if the user has opted out, False otherwise
        """
        result = self.session.execute(
            text("SELECT sms_opted_out FROM users WHERE phone_number = :phone_number"),
            {"phone_number": phone_number},
        ).fetchone()
        if result:
            return bool(result[0])
        return False
