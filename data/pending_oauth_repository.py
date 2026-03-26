"""Repository class for pending OAuth flow records."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repository import DatabaseRow, Repository


class PendingOAuthRepository(Repository):
    """Repository for managing pending OAuth flow records."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("pending_oauth", session)

    def create(
        self,
        nonce: str,
        thread_id: str,
        channel: str,
        user_email: str | None = None,
        phone_number: str | None = None,
    ) -> str:
        """Create a pending OAuth record.

        Args:
            nonce: OAuth nonce for id_token validation
            thread_id: Thread ID to resume after OAuth completes
            channel: Channel type ("email", "sms", or "web")
            user_email: User's email address (required for email/web channels)
            phone_number: User's phone number (required for SMS channel)

        Returns:
            The generated UUID used as the OAuth state parameter
        """
        pending_id = str(uuid.uuid4())
        self.insert(
            id=pending_id,
            nonce=nonce,
            thread_id=thread_id,
            channel=channel,
            user_email=user_email,
            phone_number=phone_number,
        )
        return pending_id

    def get(self, pending_id: str) -> DatabaseRow | None:
        """Get a pending OAuth record by ID.

        Args:
            pending_id: The UUID of the pending OAuth record

        Returns:
            Record tuple or None if not found
        """
        return self.get_by(id=pending_id)

    def delete_by_id(self, pending_id: str) -> None:
        """Delete a pending OAuth record after use.

        Args:
            pending_id: The UUID of the pending OAuth record
        """
        self.delete(id=pending_id)

    def cleanup_expired(self, max_age_hours: int = 24) -> None:
        """Delete pending OAuth records older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before records are cleaned up
        """
        self.session.execute(
            text(
                f"DELETE FROM {self.table_name} "
                "WHERE created_at < NOW() - MAKE_INTERVAL(hours => :hours)"
            ),
            {"hours": max_age_hours},
        )
        self.session.commit()
