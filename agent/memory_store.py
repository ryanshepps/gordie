"""Memory store singleton for the fantasy hockey assistant.

This module handles conversation memory storage and summarization.
"""

import json
import logging
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, Field

from client.duck_db_client import get_platform_db_connection

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
    players_mentioned: list[str] = Field(description="List of player names that were discussed")
    decisions_made: list[str] = Field(
        description="List of any decisions or actions the user took or decided on"
    )


def _persist_summary_to_duckdb(
    thread_id: str,
    user_email: str,
    summary: ConversationSummary,
) -> None:
    """Persist a conversation summary to DuckDB for durable storage."""
    try:
        conn = get_platform_db_connection()
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO conversation_summaries
                (thread_id, user_email, summary, key_topics, players_mentioned, decisions_made, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (thread_id) DO UPDATE SET
                summary = excluded.summary,
                key_topics = excluded.key_topics,
                players_mentioned = excluded.players_mentioned,
                decisions_made = excluded.decisions_made,
                updated_at = excluded.updated_at
            """,
            [
                thread_id,
                user_email,
                summary.summary,
                json.dumps(summary.key_topics),
                json.dumps(summary.players_mentioned),
                json.dumps(summary.decisions_made),
                now,
                now,
            ],
        )
        conn.close()
        logger.info(f"Persisted conversation summary to DuckDB for thread {thread_id}")
    except Exception as e:
        logger.error(f"Failed to persist summary to DuckDB: {e}")


def get_conversation_summaries_by_email(user_email: str) -> list[dict[str, Any]]:
    """Fetch all conversation summaries for a user from DuckDB.

    Args:
        user_email: The user's email address

    Returns:
        List of summary dicts with parsed JSON fields
    """
    conn = get_platform_db_connection()
    rows = conn.execute(
        """
        SELECT thread_id, user_email, summary, key_topics, players_mentioned,
               decisions_made, created_at, updated_at
        FROM conversation_summaries
        WHERE user_email = ?
        ORDER BY created_at DESC
        """,
        [user_email],
    ).fetchall()
    conn.close()

    return [
        {
            "thread_id": row[0],
            "user_email": row[1],
            "summary": row[2],
            "key_topics": json.loads(row[3]) if row[3] else [],
            "players_mentioned": json.loads(row[4]) if row[4] else [],
            "decisions_made": json.loads(row[5]) if row[5] else [],
            "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
            "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
        }
        for row in rows
    ]


def summarize_and_store_conversation(
    messages: list[Any],
    thread_id: str,
    user_email: str,
    store: InMemoryStore,
) -> bool:
    """
    Summarize a conversation and store it in the memory store and DuckDB.

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

        # Store in the in-memory store (for semantic search)
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

        # Persist to DuckDB (durable storage, survives restarts)
        _persist_summary_to_duckdb(thread_id, user_email, result)

        logger.info(f"Stored conversation memory for thread {thread_id}")
        logger.debug(f"Summary: {result.summary}")
        return True

    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}")
        return False
