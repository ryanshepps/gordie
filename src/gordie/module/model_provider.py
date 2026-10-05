from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel


@dataclass(frozen=True, slots=True)
class EnvironmentModels:
    provider: str
    model: str

    def chat(self, *, temperature: float = 0, model: str | None = None) -> BaseChatModel:
        chosen = model or self.model
        if self.provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=chosen, temperature=temperature)
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model_name=chosen, temperature=temperature, timeout=60, stop=None)
        raise ValueError(f"Unsupported LLM_PROVIDER: {self.provider!r}.")
