"""Web channel dispatch for the response node.

For web chat, the response is already delivered to the client via SSE
streaming. The response node only needs to log — memory storage is
handled by _store_conversation_memory which runs after dispatch.
"""

from agent.agent_state import AgentState
from module.logger import get_logger

logger = get_logger(__name__)


def send_web_response(state: AgentState, message_content: str) -> None:
    """Log that a web response was delivered via SSE.

    The actual content delivery happens through the SSE stream in chat_routes.
    This function exists to match the email/sms dispatch pattern.

    Args:
        state: Current agent state
        message_content: The AI message content (already streamed to client)
    """
    thread_id = state.get("thread_id")
    logger.info(f"Web response delivered via SSE for thread {thread_id}")
