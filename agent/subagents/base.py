"""Base utilities for sub-agents to reduce code duplication."""

import logging
import os
import sqlite3
from typing import Any, cast

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

from agent.agent_state import AgentState
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors

logger = logging.getLogger(__name__)

if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "agent_conversations.db",
)
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)


def get_checkpointer() -> SqliteSaver:
    """Return the shared SQLite checkpointer for conversation persistence."""
    return _checkpointer


def create_subagent(
    name: str,
    system_prompt: str,
    tools: list[Any],
    model: str = "gpt-4o",
    temperature: float = 0,
    response_format: type[BaseModel] | None = None,
) -> Any:
    """Create a sub-agent with standard configuration."""
    agent_kwargs: dict[str, Any] = {
        "model": ChatOpenAI(model=model, temperature=temperature),
        "tools": tools,
        "middleware": [StateLoggingMiddleware(name), handle_tool_errors],
        "system_prompt": SystemMessage(content=system_prompt),
        "checkpointer": _checkpointer,
        "state_schema": AgentState,
    }

    if response_format is not None:
        agent_kwargs["response_format"] = response_format

    return create_agent(**agent_kwargs)


def build_system_messages(
    context_parts: list[str],
) -> list[SystemMessage]:
    """Build system messages with context."""
    system_messages = []

    if context_parts:
        system_messages.append(SystemMessage(content="\n".join(context_parts)))

    return system_messages


def invoke_subagent(
    agent: Any,
    request: str,
    context_parts: list[str],
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Invoke a sub-agent with standard message building."""
    system_messages = build_system_messages(context_parts)

    input_state = {
        "messages": [*system_messages, {"role": "user", "content": request}],
    }

    config: RunnableConfig = {}
    if thread_id:
        config = {"configurable": {"thread_id": thread_id}}

    return agent.invoke(cast(Any, input_state), config)


def extract_response(
    result: dict[str, Any],
    fallback_message: str = "I encountered an issue processing your request. Please try again.",
) -> str:
    """Extract the response content from an agent result."""
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        return last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    return fallback_message
