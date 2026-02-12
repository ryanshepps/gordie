"""Async agent graph for streaming web chat responses.

Uses AsyncPostgresSaver so the graph supports astream(). Shares the same
checkpoints table as the sync graph — threads started via email/SMS can
be continued via web chat.
"""

import os

from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph
from psycopg import AsyncConnection

from agent.agent_state import AgentState
from agent.response_node import response_node
from agent.SupervisorAgent import supervisor_node
from module.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/gordie")

_async_agent = None
_async_conn: AsyncConnection | None = None


async def get_async_agent():
    """Return a cached async-capable compiled graph.

    Creates an AsyncConnection + AsyncPostgresSaver on first call,
    then reuses for the process lifetime.
    """
    global _async_agent, _async_conn

    if _async_agent is not None:
        return _async_agent

    _async_conn = await AsyncConnection.connect(
        DATABASE_URL, autocommit=True
    )
    checkpointer = AsyncPostgresSaver(_async_conn)  # pyright: ignore[reportArgumentType]
    await checkpointer.setup()

    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("response", response_node)
    workflow.set_entry_point("supervisor")

    _async_agent = workflow.compile(checkpointer=checkpointer)
    return _async_agent


async def close_async_agent() -> None:
    """Close the async connection on server shutdown."""
    global _async_agent, _async_conn

    if _async_conn is not None:
        await _async_conn.close()
        _async_conn = None
    _async_agent = None
