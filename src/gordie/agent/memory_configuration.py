import os
from dataclasses import dataclass

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    store: BaseStore
    search_enabled: bool = False


def environment_memory() -> ConversationMemory:
    if os.getenv("LLM_PROVIDER", "openai").lower() != "openai" or not os.getenv("OPENAI_API_KEY"):
        return ConversationMemory(InMemoryStore())

    from langchain_openai import OpenAIEmbeddings

    return ConversationMemory(
        InMemoryStore(
            index={"dims": 1536, "embed": OpenAIEmbeddings(model="text-embedding-3-small")}
        ),
        search_enabled=True,
    )
