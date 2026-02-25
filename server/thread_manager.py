"""
Thread management for tracking conversation threads across channels.

Handles email threading (Message-ID mapping) and SMS thread resolution
(one permanent thread per phone number).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text

from data.database import get_session
from data.sms_thread_repository import SmsThreadRepository
from module.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ThreadInfo:
    """Information about a conversation thread."""

    thread_id: str
    subject: str | None
    is_new_thread: bool


# ---------------------------------------------------------------------------
# Email thread resolution
# ---------------------------------------------------------------------------


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
        session.execute(
            text(
                """
                INSERT INTO users (email) VALUES (:email)
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"email": user_email},
        )

        session.execute(
            text(
                """
                INSERT INTO email_threads (message_id, thread_id, user_email, subject)
                VALUES (:message_id, :thread_id, :user_email, :subject)
                ON CONFLICT (message_id) DO NOTHING
                """
            ),
            {
                "message_id": message_id,
                "thread_id": thread_id,
                "user_email": user_email,
                "subject": subject,
            },
        )
        session.commit()
        logger.debug(f"Saved message_id mapping: {message_id} -> {thread_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save message_id mapping: {e}")
        raise
    finally:
        session.close()


def resolve_thread(
    user_email: str,
    in_reply_to: str | None = None,
    references: str | None = None,
    subject: str | None = None,
) -> ThreadInfo:
    """Resolve the thread_id for an incoming email."""
    # Try In-Reply-To header
    if in_reply_to:
        clean_id = in_reply_to.strip().strip("<>")
        existing_thread_id = lookup_thread_by_message_id(clean_id)

        if existing_thread_id:
            original_subject = get_thread_subject(existing_thread_id)
            logger.info(f"Found existing thread via In-Reply-To: {existing_thread_id}")
            return ThreadInfo(
                thread_id=existing_thread_id,
                subject=original_subject or subject,
                is_new_thread=False,
            )

    # Try References header
    if references:
        ref_ids = references.strip().split()
        for ref_id in ref_ids:
            clean_id = ref_id.strip().strip("<>")
            existing_thread_id = lookup_thread_by_message_id(clean_id)

            if existing_thread_id:
                original_subject = get_thread_subject(existing_thread_id)
                logger.info(f"Found existing thread via References: {existing_thread_id}")
                return ThreadInfo(
                    thread_id=existing_thread_id,
                    subject=original_subject or subject,
                    is_new_thread=False,
                )

    # New thread
    new_thread_id = f"{user_email}:{uuid.uuid4().hex[:12]}"
    logger.info(f"Creating new email thread: {new_thread_id}")

    clean_subject = subject
    if clean_subject:
        while clean_subject.lower().startswith("re:"):
            clean_subject = clean_subject[3:].strip()

    return ThreadInfo(
        thread_id=new_thread_id,
        subject=clean_subject,
        is_new_thread=True,
    )


# ---------------------------------------------------------------------------
# SMS thread resolution
# ---------------------------------------------------------------------------


def resolve_sms_thread(phone_number: str) -> ThreadInfo:
    """Resolve the thread_id for an incoming SMS.

    Each phone number maps to exactly one permanent thread. Returns the
    existing thread (updating activity) or creates a new one.
    """
    repo = SmsThreadRepository()
    try:
        latest = repo.get_latest_thread_for_phone(phone_number)

        if not latest:
            return _create_new_sms_thread(phone_number, repo)

        thread_id = str(latest[0])
        repo.update_sms_thread_activity(thread_id)
        return ThreadInfo(thread_id=thread_id, subject=None, is_new_thread=False)
    finally:
        repo.close()


def _create_new_sms_thread(phone_number: str, repo: SmsThreadRepository) -> ThreadInfo:
    """Create a new SMS thread."""
    new_thread_id = f"sms:{phone_number}:{uuid.uuid4().hex[:12]}"
    repo.create_sms_thread(new_thread_id, phone_number)
    logger.info(f"Created new SMS thread: {new_thread_id}")
    return ThreadInfo(thread_id=new_thread_id, subject=None, is_new_thread=True)
