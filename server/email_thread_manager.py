"""
Email thread management for tracking conversation threads via Message-IDs.

This module handles the mapping between email Message-IDs and conversation
thread_ids, enabling proper email threading when users reply to emails.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ThreadInfo:
    """Information about an email thread."""

    thread_id: str
    subject: str | None
    is_new_thread: bool


def lookup_thread_by_message_id(message_id: str) -> str | None:
    """
    Look up an existing thread_id by the Message-ID header.

    Args:
        message_id: The Message-ID from In-Reply-To or References header

    Returns:
        The thread_id if found, None otherwise
    """
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
    """
    Get the original subject line for a thread.

    Args:
        thread_id: The conversation thread ID

    Returns:
        The original subject if found, None otherwise
    """
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
    """
    Save a Message-ID to thread_id mapping.

    Args:
        message_id: The Message-ID of the sent email
        thread_id: The conversation thread ID
        user_email: The user's email address
        subject: The email subject line
    """
    session = get_session()
    try:
        # Ensure user exists first
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
    """
    Resolve the thread_id for an incoming email.

    If this is a reply (has In-Reply-To header), looks up the existing thread.
    Otherwise, creates a new thread_id.

    Args:
        user_email: The sender's email address
        in_reply_to: The In-Reply-To header value (Message-ID of replied email)
        references: The References header value (space-separated Message-IDs)
        subject: The email subject line

    Returns:
        ThreadInfo with thread_id, subject, and whether it's a new thread
    """
    # First, try to find existing thread via In-Reply-To
    if in_reply_to:
        # Clean the Message-ID (remove angle brackets if present)
        clean_id = in_reply_to.strip().strip("<>")
        existing_thread_id = lookup_thread_by_message_id(clean_id)

        if existing_thread_id:
            # Get the original subject from the thread
            original_subject = get_thread_subject(existing_thread_id)
            logger.info(f"Found existing thread via In-Reply-To: {existing_thread_id}")
            return ThreadInfo(
                thread_id=existing_thread_id,
                subject=original_subject or subject,
                is_new_thread=False,
            )

    # Try References header as fallback (contains all Message-IDs in thread)
    if references:
        # References is space-separated list of Message-IDs
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

    # No existing thread found - create new thread_id
    new_thread_id = f"{user_email}:{uuid.uuid4().hex[:12]}"
    logger.info(f"Creating new thread: {new_thread_id}")

    # Strip "Re: " prefixes from subject for new threads
    clean_subject = subject
    if clean_subject:
        while clean_subject.lower().startswith("re:"):
            clean_subject = clean_subject[3:].strip()

    return ThreadInfo(
        thread_id=new_thread_id,
        subject=clean_subject,
        is_new_thread=True,
    )
