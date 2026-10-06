import asyncio
from typing import cast

from langchain_core.runnables import RunnableConfig

from gordie.agent.agent_state import AgentState
from gordie.module.model_provider import DEFAULT_EMBEDDING_MODEL
from gordie.plugins import IncomingMessage, OutgoingMessage, Plugins
from gordie.runtime import Runtime


class Agent:
    def __init__(
        self,
        plugins: Plugins,
        *,
        openrouter_api_key: str,
        model: str,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.runtime = Runtime(
            plugins,
            openrouter_api_key=openrouter_api_key,
            model=model,
            embedding_model=embedding_model,
        )

    def invoke(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        from gordie.agent.graph_builder import get_agent

        with self.runtime.activate():
            return cast(AgentState, get_agent().invoke(state, config))

    async def ainvoke(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        return await asyncio.to_thread(self.invoke, state, config)

    def receive(self, message: IncomingMessage) -> OutgoingMessage | None:
        from gordie.communication import receive_message

        return self.runtime.run(receive_message, message)

    async def areceive(self, message: IncomingMessage) -> OutgoingMessage | None:
        return await asyncio.to_thread(self.receive, message)

    def close(self) -> None:
        self.runtime.close()


def create_agent(
    plugins: Plugins,
    *,
    openrouter_api_key: str,
    model: str,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> Agent:
    return Agent(
        plugins, openrouter_api_key=openrouter_api_key, model=model, embedding_model=embedding_model
    )
