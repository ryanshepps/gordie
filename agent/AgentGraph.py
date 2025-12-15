import logging
import os
import sqlite3
from typing import Any, cast

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agent.agent_state import AgentState

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


def build_agent_graph():
    """Build and return the agent graph with controller and sub-agents."""
    from agent.ControllerAgent import (
        clarification_node,
        controller_node,
        should_ask_for_clarification,
    )
    from agent.OnboardingAgent import agent as onboarding_agent

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("controller", controller_node)
    workflow.add_node("clarification", clarification_node)
    def onboarding_wrapper(state: AgentState) -> AgentState:
        # The onboarding_agent is a LangChain agent, not a LangGraph node
        # We need to call it with the appropriate input and cast the result
        input_dict: dict[str, Any] = {
            "user_email": state["user_email"],
            "messages": state["messages"]
        }
        result = onboarding_agent.invoke(cast(Any, input_dict))
        # Cast the result to AgentState - at runtime this works because
        # the agent returns a dict-like structure compatible with AgentState
        return cast(AgentState, result)

    workflow.add_node("onboarding", onboarding_wrapper)

    # Set entry point
    workflow.set_entry_point("controller")

    # Add conditional edges from controller
    workflow.add_conditional_edges(
        "controller",
        should_ask_for_clarification,
        {
            "clarify": "clarification",
            "onboarding": "onboarding",
            "continue": END,  # For now, just end - will add more agents later
        },
    )

    # Clarification and onboarding end the conversation
    workflow.add_edge("clarification", END)
    workflow.add_edge("onboarding", END)

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
