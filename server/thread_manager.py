"""
Thread management for tracking conversation threads across channels.

Handles email threading (Message-ID mapping) and SMS thread resolution
(tiered: time-based + LLM classification).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from data.database import get_session
from data.sms_thread_repository import SmsThreadRepository
from module.logger import get_logger

logger = get_logger(__name__)

# SMS thread resolution thresholds
SMS_RAPID_WINDOW_MINUTES = 5
SMS_HARD_CUTOFF_HOURS = 24


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
# SMS thread resolution (tiered: time-based + LLM classification)
# ---------------------------------------------------------------------------


def resolve_sms_thread(phone_number: str, incoming_message: str) -> ThreadInfo:
    """Resolve the thread_id for an incoming SMS.

    Tiered resolution to minimize LLM calls:
    1. No existing thread → new thread
    2. Last message >24h ago → new thread (hard cutoff)
    3. Last message <5min ago → same thread (rapid back-and-forth)
    4. Between 5min and 24h → LLM classification

    Creates an sms_threads row for new threads, updates last_message_at for
    existing threads.
    """
    repo = SmsThreadRepository()
    try:
        latest = repo.get_latest_thread_for_phone(phone_number)

        if not latest:
            return _create_new_sms_thread(phone_number, repo)

        thread_id = str(latest[0])
        last_message_at = latest[2]
        now = datetime.now(UTC)

        # Ensure last_message_at is timezone-aware
        if last_message_at.tzinfo is None:
            last_message_at = last_message_at.replace(tzinfo=UTC)

        elapsed = now - last_message_at

        # Hard cutoff: over 24 hours → new thread
        if elapsed > timedelta(hours=SMS_HARD_CUTOFF_HOURS):
            logger.info(f"SMS thread expired (>{SMS_HARD_CUTOFF_HOURS}h), creating new thread")
            return _create_new_sms_thread(phone_number, repo)

        # Rapid window: under 5 minutes → same thread
        if elapsed < timedelta(minutes=SMS_RAPID_WINDOW_MINUTES):
            logger.info(f"SMS rapid back-and-forth (<{SMS_RAPID_WINDOW_MINUTES}min), continuing thread")
            repo.update_sms_thread_activity(thread_id)
            return ThreadInfo(thread_id=thread_id, subject=None, is_new_thread=False)

        # Middle zone: use LLM classification
        from server.sms_intent_classifier import is_same_conversation

        if is_same_conversation(thread_id, incoming_message):
            logger.info("LLM classified SMS as same conversation, continuing thread")
            repo.update_sms_thread_activity(thread_id)
            return ThreadInfo(thread_id=thread_id, subject=None, is_new_thread=False)

        logger.info("LLM classified SMS as new conversation, creating new thread")
        return _create_new_sms_thread(phone_number, repo)

    finally:
        repo.close()


def _create_new_sms_thread(phone_number: str, repo: SmsThreadRepository) -> ThreadInfo:
    """Create a new SMS thread."""
    new_thread_id = f"sms:{phone_number}:{uuid.uuid4().hex[:12]}"
    repo.create_sms_thread(new_thread_id, phone_number)
    logger.info(f"Created new SMS thread: {new_thread_id}")
    return ThreadInfo(thread_id=new_thread_id, subject=None, is_new_thread=True)
