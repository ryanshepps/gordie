import asyncio
from typing import cast

from langchain_core.runnables import RunnableConfig

from gordie.agent.agent_state import AgentState
from gordie.plugins import Plugins
from gordie.runtime import Runtime


class Agent:
    def __init__(self, plugins: Plugins) -> None:
        self.runtime = Runtime(plugins)

    def invoke(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        from gordie.agent.graph_builder import get_agent

        with self.runtime.activate():
            return cast(AgentState, get_agent().invoke(state, config))

    async def ainvoke(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        return await asyncio.to_thread(self.invoke, state, config)

    def close(self) -> None:
        self.runtime.close()


def create_agent(plugins: Plugins) -> Agent:
    return Agent(plugins)
