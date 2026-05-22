import builtins
import importlib

from langgraph.store.memory import InMemoryStore

from tools.memory.search_past_conversations import create_search_past_conversations_tool


def test_anthropic_provider_without_openai_key_creates_plain_memory_store(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    original_import = builtins.__import__

    def fail_on_openai_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "langchain_openai":
            raise AssertionError("langchain_openai should not be imported for Anthropic memory")
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_on_openai_import)

    import agent.memory_store as memory_store

    memory_store = importlib.reload(memory_store)

    store = memory_store.get_memory_store()

    assert isinstance(store, InMemoryStore)
    assert not memory_store.is_memory_search_enabled()


def test_memory_search_tool_is_cleanly_disabled():
    store = InMemoryStore()
    search_tool = create_search_past_conversations_tool(store, enabled=False)

    result = search_tool.func(  # pyright: ignore[reportAttributeAccessIssue]
        "McDavid trade", state={"user_id": "user-123"}
    )

    assert result == "Past conversation search is currently unavailable."
