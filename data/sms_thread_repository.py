"""Repository class for SMS thread records."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


class SmsThreadRepository:
    """Repository for managing SMS conversation threads."""

    def __init__(self, session: Session | None = None) -> None:
        self._owns_session = session is None
        self.session = session or get_session()

    def get_latest_thread_for_phone(self, phone_number: str) -> tuple[Any, ...] | None:
        """Get the most recent SMS thread for a phone number.

        Args:
            phone_number: The phone number to look up

        Returns:
            Record tuple (thread_id, phone_number, last_message_at, created_at) or None
        """
        result = self.session.execute(
            text(
                """
                SELECT thread_id, phone_number, last_message_at, created_at
                FROM sms_threads
                WHERE phone_number = :phone_number
                ORDER BY last_message_at DESC
                LIMIT 1
                """
            ),
            {"phone_number": phone_number},
        ).fetchone()
        return cast(tuple[Any, ...] | None, result)

    def create_sms_thread(self, thread_id: str, phone_number: str) -> None:
        """Create a new SMS thread record.

        Args:
            thread_id: The conversation thread_id
            phone_number: The phone number for this thread
        """
        self.session.execute(
            text(
                """
                INSERT INTO sms_threads (thread_id, phone_number)
                VALUES (:thread_id, :phone_number)
                """
            ),
            {"thread_id": thread_id, "phone_number": phone_number},
        )
        self.session.commit()

    def update_sms_thread_activity(self, thread_id: str) -> None:
        """Update last_message_at for an SMS thread.

        Args:
            thread_id: The conversation thread_id
        """
        self.session.execute(
            text(
                """
                UPDATE sms_threads SET last_message_at = NOW()
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": thread_id},
        )
        self.session.commit()

    def get_last_message_time(self, thread_id: str) -> datetime | None:
        """Get the last message timestamp for a thread.

        Args:
            thread_id: The conversation thread_id

        Returns:
            The last_message_at timestamp or None if not found
        """
        result = self.session.execute(
            text("SELECT last_message_at FROM sms_threads WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        ).fetchone()
        if result:
            return result[0]
        return None

    def close(self) -> None:
        """Close the session if owned by this repository."""
        if self._owns_session and self.session:
            self.session.close()
