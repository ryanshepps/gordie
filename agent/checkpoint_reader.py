"""Shared checkpoint reader for extracting messages from conversation tables."""

from typing import Any

from data.conversation_repository import ConversationRepository
from module.logger import get_logger

logger = get_logger(__name__)


def get_messages_from_checkpoint(thread_id: str) -> list[dict[str, Any]]:
    """Read user-visible messages from conversation_messages table.

    Args:
        thread_id: The conversation thread ID

    Returns:
        List of message dicts with role, content, and timestamp
    """
    try:
        with ConversationRepository() as repo:
            messages = repo.get_messages(thread_id)

        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
            if msg["role"] in ("human", "ai")
        ]

    except Exception as e:
        logger.error(f"Failed to get messages for thread {thread_id}: {e}")
        return []
