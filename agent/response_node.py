"""Response node for the fantasy hockey assistant graph.

Dispatches responses to the appropriate channel (email, SMS, web).
"""

from typing import Literal

from langgraph.types import Command

from agent.agent_state import AgentState
from agent.channels.email_channel import send_email_response
from agent.memory_store import get_memory_store, summarize_and_store_conversation
from module.logger import get_logger
from tools.send_acknowledgement import _extract_phone_from_thread_id, _send_sms

logger = get_logger(__name__)

END_NODE: Literal["__end__"] = "__end__"


def _get_last_ai_message(messages: list[object]) -> tuple[str | None, object | None]:
    """Extract the last AI message content from the message list."""
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", None)
        if msg_type is None and isinstance(msg, dict):
            msg_type = msg.get("type")
        if msg_type == "ai":
            if isinstance(msg, dict):
                return str(msg.get("content", "")), msg
            else:
                content = getattr(msg, "content", None)
                if content is not None:
                    return str(content), msg
                return str(msg), msg
    return None, None


def _store_conversation_memory(state: AgentState, messages: list[object]) -> None:
    """Store conversation summary after response dispatch."""
    thread_id = state.get("thread_id")
    user_email = state.get("user_email")
    if thread_id and user_email:
        try:
            summarize_and_store_conversation(
                messages=messages,
                thread_id=thread_id,
                user_email=user_email,
                store=get_memory_store(),
            )
        except Exception as e:
            logger.error(f"Failed to store conversation memory: {e}")


def response_node(state: AgentState) -> Command[Literal["__end__"]]:
    """Dispatch the agent response to the appropriate channel and end the flow."""
    messages = state.get("messages", [])
    channel = state.get("channel", "email")

    # SMS: the ack was sent inline via send_acknowledgement. The final
    # response is delivered here as a single SMS to guarantee ordering.
    if channel == "sms":
        message_content, _ = _get_last_ai_message(messages)
        if message_content:
            thread_id = state.get("thread_id", "")
            try:
                phone_number = _extract_phone_from_thread_id(thread_id)
                _send_sms(phone_number, message_content)
                logger.info("SMS response sent via response_node")
            except (ValueError, RuntimeError) as e:
                logger.error(f"Failed to send SMS response: {e}")
        else:
            logger.warning("No AI message found to send via SMS")
        _store_conversation_memory(state, messages)
        return Command(goto=END_NODE, update=state)

    message_content, _ = _get_last_ai_message(messages)

    if not message_content:
        logger.warning("No AI message found to send")
        return Command(goto=END_NODE, update=state)

    if channel == "email":
        send_email_response(state, message_content)
    else:
        logger.error(f"Unknown channel: {channel}")

    _store_conversation_memory(state, messages)

    return Command(goto=END_NODE, update=state)
