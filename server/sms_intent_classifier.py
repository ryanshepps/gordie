"""SMS intent classifier for thread resolution.

Uses a fast LLM call to determine if an incoming SMS is a continuation
of the current conversation or a new topic.
"""

from sqlalchemy import text

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


def _get_conversation_summary(thread_id: str) -> str | None:
    """Load the conversation summary for a thread."""
    session = get_session()
    try:
        result = session.execute(
            text("SELECT summary FROM conversation_summaries WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        ).fetchone()
        if result and result[0]:
            return str(result[0])
        return None
    finally:
        session.close()


def is_same_conversation(thread_id: str, incoming_message: str) -> bool:
    """Classify whether an incoming SMS is part of the existing conversation.

    Uses a fast/cheap LLM call with structured output. Defaults to True
    (same thread) on any failure to avoid splitting mid-conversation.

    Args:
        thread_id: The current thread ID
        incoming_message: The new SMS message text

    Returns:
        True if the message is a continuation, False if it's a new topic
    """
    try:
        summary = _get_conversation_summary(thread_id)
        if not summary:
            # No summary yet — likely very early in conversation, assume same thread
            return True

        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=50,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify whether a new message is a continuation of an existing "
                        "conversation or an unrelated new request. "
                        'Respond with JSON: {"same_conversation": true} or {"same_conversation": false}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation summary:\n{summary}\n\n"
                        f"New message:\n{incoming_message}\n\n"
                        "Is this new message a continuation of the same topic?"
                    ),
                },
            ],
        )

        import json

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        return bool(result.get("same_conversation", True))

    except Exception as e:
        logger.warning(f"SMS intent classification failed, defaulting to same thread: {e}")
        return True
