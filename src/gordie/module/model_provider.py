from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


@dataclass(frozen=True, slots=True)
class OpenRouterModels:
    api_key: str = field(repr=False)
    model: str
    embedding_model: str = DEFAULT_EMBEDDING_MODEL

    def chat(self, *, temperature: float = 0, model: str | None = None) -> BaseChatModel:
        return ChatOpenAI(
            api_key=SecretStr(self.api_key),
            base_url=OPENROUTER_BASE_URL,
            model=model or self.model,
            temperature=temperature,
        )

    def embeddings(self) -> OpenAIEmbeddings:
        return OpenAIEmbeddings(
            api_key=SecretStr(self.api_key),
            base_url=OPENROUTER_BASE_URL,
            model=self.embedding_model,
            check_embedding_ctx_length=False,
        )
