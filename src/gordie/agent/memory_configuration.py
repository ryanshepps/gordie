from dataclasses import dataclass

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from gordie.module.model_provider import OpenRouterModels


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    store: BaseStore
    search_enabled: bool = False


def environment_memory(models: OpenRouterModels) -> ConversationMemory:
    return ConversationMemory(
        InMemoryStore(index={"dims": models.embedding_dimensions, "embed": models.embeddings()}),
        search_enabled=True,
    )
