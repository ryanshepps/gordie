from langchain_core.language_models import BaseChatModel

from gordie.runtime import current_runtime


def make_llm(temperature: float = 0, model: str | None = None) -> BaseChatModel:
    runtime = current_runtime()
    return runtime.resource(
        f"model:{temperature}:{model}",
        lambda: runtime.plugins.models.chat(temperature=temperature, model=model),
    )
