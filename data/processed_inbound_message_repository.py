"""Repository for inbound webhook idempotency."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import Repository


class ProcessedInboundMessageRepository(Repository):
    """Track external inbound message IDs that have already been accepted."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("processed_inbound_messages", session)

    def claim(
        self,
        medium: Medium,
        external_message_id: str,
        external_sender_id: str,
    ) -> bool:
        """Record an inbound message if unseen.

        Returns True when this process claimed the message, False when another
        request already recorded it.
        """
        result = self.session.execute(
            text(
                """
                INSERT INTO processed_inbound_messages
                    (medium, external_message_id, external_sender_id)
                VALUES (:medium, :external_message_id, :external_sender_id)
                ON CONFLICT (medium, external_message_id) DO NOTHING
                RETURNING 1
                """
            ),
            {
                "medium": medium.value,
                "external_message_id": external_message_id,
                "external_sender_id": external_sender_id,
            },
        ).fetchone()
        self.session.commit()
        return result is not None

    def cleanup_expired(self, max_age_hours: int = 24) -> None:
        """Delete processed inbound message records older than max_age_hours."""
        self.session.execute(
            text(
                "DELETE FROM processed_inbound_messages "
                "WHERE created_at < NOW() - MAKE_INTERVAL(hours => :hours)"
            ),
            {"hours": max_age_hours},
        )
        self.session.commit()
