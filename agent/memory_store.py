"""Memory store singleton for the fantasy hockey assistant.

This module handles conversation memory storage and summarization.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Memory store singleton - lazily initialized to avoid import-time API key requirements
_memory_store: InMemoryStore | None = None


def get_memory_store() -> InMemoryStore:
    """Get or create the memory store singleton with semantic search."""
    global _memory_store
    if _memory_store is None:
        _memory_store = InMemoryStore(
            index={
                "dims": 1536,
                "embed": OpenAIEmbeddings(model="text-embedding-3-small"),
            }
        )
    return _memory_store


# For backwards compatibility - will be initialized on first access
# Note: This will fail at import time if OPENAI_API_KEY is not set
# Use get_memory_store() for lazy initialization
memory_store: InMemoryStore | None = None


def _sanitize_namespace_label(label: str) -> str:
    """
    Sanitize a string for use in LangGraph store namespace.

    LangGraph namespaces cannot contain periods, so we replace them.

    Args:
        label: The label to sanitize (e.g., email address)

    Returns:
        Sanitized label safe for namespace use
    """
    return label.replace(".", "_dot_").replace("@", "_at_")


class ConversationSummary(BaseModel):
    """Structured output for conversation summarization."""

    summary: str = Field(
        description="A concise 2-3 sentence summary of what was discussed and any outcomes"
    )
    key_topics: list[str] = Field(
        description="List of main topics discussed (e.g., 'trade advice', 'waiver pickup')"
    )
    players_mentioned: list[str] = Field(
        description="List of player names that were discussed"
    )
    decisions_made: list[str] = Field(
        description="List of any decisions or actions the user took or decided on"
    )


def summarize_and_store_conversation(
    messages: list[Any],
    thread_id: str,
    user_email: str,
    store: InMemoryStore,
) -> bool:
    """
    Summarize a conversation and store it in the memory store.

    Args:
        messages: List of conversation messages
        thread_id: The conversation thread ID
        user_email: The user's email address
        store: The LangGraph memory store

    Returns:
        True if stored successfully, False otherwise
    """
    # Need at least 2 messages (user + assistant) to summarize
    if not messages or len(messages) < 2:
        logger.debug("Not enough messages to summarize")
        return False

    # Check if we already have a memory for this thread
    safe_email = _sanitize_namespace_label(user_email)
    namespace = ("memories", safe_email)
    existing = store.get(namespace, thread_id)
    if existing:
        logger.debug(f"Memory already exists for thread {thread_id}")
        return False

    # Build conversation text from messages
    conversation_parts = []
    for msg in messages:
        if hasattr(msg, "type") and hasattr(msg, "content"):
            role = "User" if msg.type == "human" else "Gordie"
            content = str(msg.content)
            if content and not content.startswith("system"):
                conversation_parts.append(f"{role}: {content}")
        elif isinstance(msg, dict):
            msg_type = msg.get("type") or msg.get("role")
            role = "User" if msg_type in ("human", "user") else "Gordie"
            content = msg.get("content", "")
            if content:
                conversation_parts.append(f"{role}: {content}")

    if len(conversation_parts) < 2:
        return False

    conversation_text = "\n\n".join(conversation_parts[-10:])  # Last 10 messages max

    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = model.with_structured_output(ConversationSummary)

        prompt = f"""Analyze this fantasy hockey conversation and extract key information.

Conversation:
{conversation_text}

Generate a summary that captures:
1. What the user asked about or wanted help with
2. What advice or information was provided
3. Any decisions the user made
4. Players that were specifically discussed"""

        result: Any = structured_llm.invoke(prompt)

        # Store in the memory store
        store.put(
            namespace,
            thread_id,
            {
                "summary": result.summary,
                "key_topics": result.key_topics,
                "players_mentioned": result.players_mentioned,
                "decisions_made": result.decisions_made,
                "created_at": datetime.now().isoformat(),
                "thread_id": thread_id,
            },
        )

        logger.info(f"Stored conversation memory for thread {thread_id}")
        logger.debug(f"Summary: {result.summary}")
        return True

    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}")
        return False
