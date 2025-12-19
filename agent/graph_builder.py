"""Agent graph for the fantasy hockey assistant.

Uses a simplified supervisor pattern where sub-agents are invoked as tools
rather than separate graph nodes. This provides deterministic routing
through explicit tool calls.
"""

import logging
import os
import sqlite3
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.types import Command

from agent.agent_state import AgentState

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)


def is_first_message_in_thread(thread_id: str) -> bool:
    """
    Check if this is the first message in the current conversation thread.

    Args:
        thread_id: The conversation thread ID

    Returns:
        True if no previous checkpoints exist for this thread, False otherwise
    """
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )

    if not os.path.exists(db_path):
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM checkpoints
            WHERE thread_id = ?
        """,
            (thread_id,),
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count == 0

    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return True


def email_node(state: AgentState) -> Command[Literal["__end__"]]:
    """Sends email to user with agent response and ends the flow."""
    from tools.email.send_email import send_email

    # Extract last assistant message
    messages = state.get("messages", [])
    user_email = state.get("user_email")

    if not user_email:
        logger.error("No user email found in state, cannot send email")
        return Command(goto=END_NODE, update=state)

    # Find last AI message
    last_ai_message = None
    for msg in reversed(messages):
        # Check if it's an AI message (has .type attribute or is dict with 'type' key)
        msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
        if msg_type == 'ai':
            last_ai_message = msg
            break

    if not last_ai_message:
        logger.warning("No AI message found to send via email")
        return Command(goto=END_NODE, update=state)

    # Extract message content
    if isinstance(last_ai_message, dict):
        message_content = str(last_ai_message.get("content", ""))
    elif hasattr(last_ai_message, "content"):
        message_content = str(last_ai_message.content)
    else:
        message_content = str(last_ai_message)

    # Determine email subject based on message content
    message_lower = message_content.lower()
    if "comparison" in message_lower or "vs" in message_lower or "recommend" in message_lower:
        subject = "Fantasy Hockey Player Comparison"
    elif "onboard" in message_lower or "connect" in message_lower or "authenticate" in message_lower:
        subject = "Fantasy Hockey Team Setup"
    else:
        subject = "Fantasy Hockey Assistant Response"

    # Call send_email tool
    try:
        result = send_email.invoke({
            "to_email": user_email,
            "subject": subject,
            "message": message_content
        })
        logger.info(f"Email send result: {result}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

    return Command(goto=END_NODE, update=state)


def build_agent_graph():
    """Build and return the simplified agent graph.

    The graph now has only 3 nodes:
    - controller: Supervisor that handles requests via sub-agent tools
    - clarification: Asks user for more information when needed
    - email: Sends the response to the user

    Sub-agents (onboarding, player_comparison) are now invoked as tools
    by the supervisor rather than being separate graph nodes.
    """
    from agent.ControllerAgent import (
        clarification_node,
        controller_node,
    )

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes - sub-agents are now tools, not nodes
    workflow.add_node("controller", controller_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("email", email_node)

    # Set entry point
    workflow.set_entry_point("controller")

    # Setup persistent checkpointer
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # Compile the graph
    return workflow.compile(checkpointer=checkpointer)


# Build the agent graph
agent = build_agent_graph()
