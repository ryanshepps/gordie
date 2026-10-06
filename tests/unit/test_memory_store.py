from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore
from pydantic import SecretStr

from gordie import create_app
from gordie.integrations.defaults import default_plugins
from gordie.module.model_provider import OpenRouterModels
from gordie.tools.memory.search_past_conversations import create_search_past_conversations_tool


def test_openrouter_memory_search_uses_app_embeddings() -> None:
    app = create_app(
        default_plugins(),
        openrouter_api_key="test-key",
        model="z-ai/glm-5.3-flash",
        embedding_model="test/embedding-model",
        embedding_dimensions=768,
    )
    memory = app.runtime.memory

    assert isinstance(memory.store, InMemoryStore)
    assert memory.search_enabled
    assert memory.store.index_config is not None
    embeddings = memory.store.index_config.get("embed")
    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.model == "test/embedding-model"
    assert memory.store.index_config.get("dims") == 768
    assert isinstance(embeddings.openai_api_key, SecretStr)
    assert embeddings.openai_api_key.get_secret_value() == "test-key"
    assert embeddings.openai_api_base == "https://openrouter.ai/api/v1"
    app.runtime.close()


def test_openrouter_chat_uses_configured_model_without_exposing_key() -> None:
    models = OpenRouterModels("test-secret-key", "z-ai/glm-5.3-flash")
    chat = models.chat()

    assert isinstance(chat, ChatOpenAI)
    assert chat.model_name == "z-ai/glm-5.3-flash"
    assert chat.openai_api_base == "https://openrouter.ai/api/v1"
    assert "test-secret-key" not in repr(models)
    assert "test-secret-key" not in repr(chat)


def test_memory_search_tool_is_cleanly_disabled():
    store = InMemoryStore()
    search_tool = create_search_past_conversations_tool(store, enabled=False)

    result = search_tool.func(  # pyright: ignore[reportAttributeAccessIssue]
        "McDavid trade", state={"user_id": "user-123"}
    )

    assert result == "Past conversation search is currently unavailable."
