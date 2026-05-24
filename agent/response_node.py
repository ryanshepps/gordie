"""Response node for the fantasy sports assistant graph.

Dispatches responses through the configured channel adapter.
"""

from collections.abc import Callable, Mapping
from typing import Literal, cast

from langgraph.types import Command

from agent.agent_state import AgentState
from agent.memory_store import get_memory_store, summarize_and_store_conversation
from data.models import Medium
from module.logger import get_logger
from server.adapters.base import AdapterRegistry

logger = get_logger(__name__)

END_NODE: Literal["__end__"] = "__end__"


def _get_last_ai_message(messages: list[object]) -> tuple[str | None, object | None]:
    """Extract the last AI message content from the message list."""
    for msg in reversed(messages):
        msg_type = cast(object | None, getattr(msg, "type", None))
        if msg_type is None and isinstance(msg, Mapping):
            msg_map = cast(Mapping[str, object], msg)
            msg_type = msg_map.get("type")
        if msg_type == "ai":
            if isinstance(msg, Mapping):
                msg_map = cast(Mapping[str, object], msg)
                return str(msg_map.get("content", "")), cast(object, msg)

            content = cast(object | None, getattr(msg, "content", None))
            if content is not None:
                return str(content), msg
            return str(msg), msg
    return None, None


def _store_conversation_memory(state: AgentState, messages: list[object]) -> None:
    """Store conversation summary after response dispatch."""
    thread_id = state.get("thread_id")
    user_id = state.get("user_id")
    if thread_id and user_id:
        try:
            _ = summarize_and_store_conversation(
                messages=messages,
                thread_id=thread_id,
                user_id=user_id,
                store=get_memory_store(),
            )
        except Exception as e:
            logger.error(f"Failed to store conversation memory: {e}")


def _coerce_medium(channel: object) -> Medium | None:
    if isinstance(channel, Medium):
        return channel
    if isinstance(channel, str):
        try:
            return Medium(channel)
        except ValueError:
            return None
    return None


def make_response_node(
    registry: AdapterRegistry,
) -> Callable[[AgentState], Command[Literal["__end__"]]]:
    def response_node(state: AgentState) -> Command[Literal["__end__"]]:
        """Dispatch the agent response to the appropriate channel and end the flow."""
        messages = state.get("messages", [])
        channel = cast(object, state.get("channel"))
        external_id = state.get("external_id")

        message_content, _ = _get_last_ai_message(messages)
        if not message_content:
            logger.warning("No AI message found to send")
            return Command(goto=END_NODE, update=state)

        if channel == "cli" or state.get("dispatch_response") is False:
            _store_conversation_memory(state, messages)
            return Command(goto=END_NODE, update=state)

        medium = _coerce_medium(channel)
        if medium is None:
            logger.error(f"No valid channel found in state: {channel}")
        elif not external_id:
            logger.error("No external_id found in state")
        else:
            adapter = registry.get(medium)
            if adapter:
                adapter.send(external_id, message_content, state)
            else:
                logger.error(f"No adapter configured for channel: {medium.value}")

        _store_conversation_memory(state, messages)
        return Command(goto=END_NODE, update=state)

    return response_node
