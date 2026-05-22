"""Email Message-ID mapping helpers."""

from sqlalchemy import text

from data.database import get_session
from data.models import Medium
from data.user_repository import UserRepository
from module.logger import get_logger

logger = get_logger(__name__)


def lookup_thread_by_message_id(message_id: str) -> str | None:
    """Look up an existing thread_id by the email Message-ID header."""
    session = get_session()
    try:
        result = session.execute(
            text("SELECT thread_id FROM email_threads WHERE message_id = :message_id"),
            {"message_id": message_id},
        ).fetchone()

        if result:
            return str(result[0])
        return None
    finally:
        session.close()


def get_thread_subject(thread_id: str) -> str | None:
    """Get the original subject line for an email thread."""
    session = get_session()
    try:
        result = session.execute(
            text(
                """
                SELECT subject FROM email_threads
                WHERE thread_id = :thread_id
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id},
        ).fetchone()

        if result:
            return str(result[0]) if result[0] else None
        return None
    finally:
        session.close()


def save_message_id_mapping(
    message_id: str,
    thread_id: str,
    user_email: str,
    subject: str | None = None,
) -> None:
    """Save a Message-ID to thread_id mapping for email threading."""
    session = get_session()
    try:
        user_repo = UserRepository(session)
        user_id = user_repo.resolve_user_id(Medium.EMAIL, user_email, user_email)

        session.execute(
            text(
                """
                INSERT INTO email_threads (message_id, thread_id, user_id, subject)
                VALUES (:message_id, :thread_id, :user_id, :subject)
                ON CONFLICT (message_id) DO NOTHING
                """
            ),
            {
                "message_id": message_id,
                "thread_id": thread_id,
                "user_id": user_id,
                "subject": subject,
            },
        )
        session.commit()
        logger.debug(f"Saved message_id mapping: {message_id} -> {thread_id}")
    except Exception as exc:
        session.rollback()
        logger.error(f"Failed to save message_id mapping: {exc}")
        raise
    finally:
        session.close()
