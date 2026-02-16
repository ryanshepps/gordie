"""Async agent graph for streaming web chat responses.

Uses AsyncCustomCheckpointer so the graph supports astream(). Shares the same
conversation tables as the sync graph — threads started via email/SMS can
be continued via web chat.
"""

from langgraph.graph import StateGraph

from agent.agent_state import AgentState
from agent.async_custom_checkpointer import AsyncCustomCheckpointer
from agent.response_node import response_node
from agent.SupervisorAgent import supervisor_node
from module.logger import get_logger

logger = get_logger(__name__)

_async_agent = None
_async_checkpointer: AsyncCustomCheckpointer | None = None


async def get_async_agent():
    """Return a cached async-capable compiled graph.

    Creates an AsyncCustomCheckpointer on first call,
    then reuses for the process lifetime.
    """
    global _async_agent, _async_checkpointer

    if _async_agent is not None:
        return _async_agent

    _async_checkpointer = AsyncCustomCheckpointer()
    await _async_checkpointer.setup()

    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("response", response_node)
    workflow.set_entry_point("supervisor")

    _async_agent = workflow.compile(checkpointer=_async_checkpointer)
    return _async_agent


async def close_async_agent() -> None:
    """Close the async agent on server shutdown."""
    global _async_agent, _async_checkpointer

    _async_agent = None
    _async_checkpointer = None
