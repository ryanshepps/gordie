"""Base utilities for sub-agents to reduce code duplication."""

from typing import Any, cast

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from module.logger import get_logger

logger = get_logger(__name__)


def get_checkpointer():
    """Return the shared PostgreSQL checkpointer for conversation persistence."""
    return checkpointer


def create_subagent(
    name: str,
    system_prompt: str,
    tools: list[Any],
    model: str = "gpt-4o",
    temperature: float = 0,
    response_format: type[BaseModel] | None = None,
) -> Any:
    """Create a sub-agent with standard configuration."""
    llm = ChatOpenAI(model=model, temperature=temperature).bind(
        parallel_tool_calls=False,
    )
    agent_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools,
        "middleware": [StateLoggingMiddleware(name), handle_tool_errors],
        "system_prompt": SystemMessage(content=system_prompt),
        "checkpointer": checkpointer,
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
