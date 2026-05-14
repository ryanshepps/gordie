"""LLM client factory — selects provider based on module.config.

Centralises model instantiation so every call site (supervisor, sub-agents,
digest writer, voice rewriter, quality checks) picks up `LLM_PROVIDER` /
`LLM_MODEL` env overrides automatically.
"""

from langchain_core.language_models import BaseChatModel

from module.config import LLM_MODEL, LLM_PROVIDER


def make_llm(temperature: float = 0, model: str | None = None) -> BaseChatModel:
    """Construct a chat LLM client using configured provider + model.

    Args:
        temperature: Sampling temperature.
        model: Override the configured model name (rare — usually defer to env).

    Returns:
        A LangChain chat model ready to invoke.

    Raises:
        ValueError: If LLM_PROVIDER is set to an unsupported value.
    """
    chosen = model or LLM_MODEL
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=chosen, temperature=temperature)
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model_name=chosen, temperature=temperature, timeout=60, stop=None)
    raise ValueError(
        f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r}. Expected 'openai' or 'anthropic'."
    )
