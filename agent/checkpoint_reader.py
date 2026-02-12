"""Shared checkpoint reader for extracting messages from LangGraph checkpoints."""

from typing import Any

from langchain_core.runnables.config import RunnableConfig

from agent.checkpointer import checkpointer
from module.logger import get_logger

logger = get_logger(__name__)


def get_messages_from_checkpoint(thread_id: str) -> list[dict[str, Any]]:
    """Read LangGraph checkpoint data and extract human/AI message pairs.

    Args:
        thread_id: The conversation thread ID

    Returns:
        List of message dicts with role, content, and timestamp
    """
    try:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        state = checkpointer.get_tuple(config)

        if not state:
            return []

        channel_values = state.checkpoint.get("channel_values", {})
        messages_raw: list[Any] = channel_values.get("messages", [])

        messages: list[dict[str, Any]] = []
        for msg in messages_raw:
            role: str | None = None
            content = ""

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

            if not role or not content or isinstance(content, list):
                continue

            messages.append({"role": role, "content": content})

        return messages

    except Exception as e:
        logger.error(f"Failed to extract messages from checkpoint: {e}")
        return []
