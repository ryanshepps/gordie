"""Memory store singleton for the fantasy hockey assistant.

This module is separated from graph_builder to avoid circular imports.
"""

from langchain_openai import OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore

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
