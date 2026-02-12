"""Shared checkpoint reader for extracting messages from LangGraph checkpoints."""

from typing import Any

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import text

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


def get_messages_from_checkpoint(thread_id: str) -> list[dict[str, Any]]:
    """Read LangGraph checkpoint data and extract human/AI message pairs.

    Args:
        thread_id: The conversation thread ID

    Returns:
        List of message dicts with role, content, and timestamp
    """
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT type, checkpoint
                FROM checkpoints
                WHERE thread_id = :thread_id
                ORDER BY checkpoint_id DESC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id},
        ).fetchall()

        if not rows:
            return []

        serde = JsonPlusSerializer()
        checkpoint_data: dict[str, Any] = serde.loads_typed((rows[0][0], rows[0][1]))

        channel_values = checkpoint_data.get("channel_values", {})
        messages_raw: list[Any] = channel_values.get("messages", [])

        messages: list[dict[str, Any]] = []
        for msg in messages_raw:
            role: str | None = None
            content = ""
            timestamp = ""

            if hasattr(msg, "type"):
                if msg.type == "human":
                    role = "human"
                elif msg.type == "ai":
                    role = "ai"
                content = str(msg.content) if hasattr(msg, "content") else ""
            elif isinstance(msg, dict):
                msg_type = msg.get("type") or msg.get("role", "")
                if msg_type in ("human", "user"):
                    role = "human"
                elif msg_type in ("ai", "assistant"):
                    role = "ai"
                content = msg.get("content", "")

            if not role or not content:
                continue

            if isinstance(content, list):
                continue

            additional_kwargs: dict[str, Any] = getattr(msg, "additional_kwargs", {})
            response_metadata: dict[str, Any] = getattr(msg, "response_metadata", {})
            timestamp = additional_kwargs.get("timestamp", "") or response_metadata.get(
                "timestamp", ""
            )

            messages.append({"role": role, "content": content, "timestamp": timestamp})

        return messages

    except Exception as e:
        logger.error(f"Failed to extract messages from checkpoint: {e}")
        return []
    finally:
        session.close()
