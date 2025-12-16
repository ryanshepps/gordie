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


def flow_coordinator_node(state: AgentState) -> AgentState:
    """Advances flow index and checks for completion."""
    agent_flow = state.get("agent_flow", [])
    current_index = state.get("current_agent_index", 0)

    # Safety check: if flow is already complete, don't increment
    if state.get("flow_complete"):
        logger.warning("Flow already marked complete, skipping coordinator increment")
        return state

    # Increment the agent index
    state["current_agent_index"] = current_index + 1

    # Check if flow is complete
    if state["current_agent_index"] >= len(agent_flow):
        state["flow_complete"] = True
        logger.info(f"Flow complete. Processed {state['current_agent_index']} agents.")
    else:
        logger.info(
            f"Flow coordinator: moving to agent {state['current_agent_index'] + 1}/"
            f"{len(agent_flow)}"
        )

    return state


def email_node(state: AgentState) -> AgentState:
    """Sends email to user with agent response."""
    from tools.email.send_email import send_email

    # Extract last assistant message
    messages = state.get("messages", [])
    user_email = state.get("user_email")

    if not user_email:
        logger.error("No user email found in state, cannot send email")
        return state

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
        return state

    # Extract message content
    if isinstance(last_ai_message, dict):
        message_content = str(last_ai_message.get("content", ""))
    elif hasattr(last_ai_message, "content"):
        message_content = str(last_ai_message.content)
    else:
        message_content = str(last_ai_message)

    # Compose email subject based on agent flow
    agent_flow = state.get("agent_flow", [])
    if "player_comparison" in agent_flow:
        subject = "Fantasy Hockey Player Comparison"
    elif "onboarding" in agent_flow:
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

    return state


def build_agent_graph():
    """Build and return the agent graph with controller and sub-agents."""
    from agent.ControllerAgent import (
        clarification_node,
        controller_node,
        route_to_next_agent,
    )
    from agent.OnboardingAgent import agent as onboarding_agent
    from agent.PlayerComparisonAgent import agent as player_comparison_agent

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("controller", controller_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("flow_coordinator", flow_coordinator_node)
    workflow.add_node("email", email_node)

    def onboarding_wrapper(state: AgentState) -> AgentState:
        # The onboarding_agent is a LangChain agent, not a LangGraph node
        # We need to call it with the appropriate input and cast the result
        try:
            input_dict: dict[str, Any] = {
                "user_email": state["user_email"],
                "messages": state["messages"]
            }
            result = onboarding_agent.invoke(cast(Any, input_dict))
            # Cast the result to AgentState - at runtime this works because
            # the agent returns a dict-like structure compatible with AgentState
            return cast(AgentState, result)
        except Exception as e:
            logger.error(f"Error in onboarding agent: {e}", exc_info=True)
            # Mark flow as complete and route to clarification on error
            state["flow_complete"] = True
            state["needs_clarification"] = True
            return state

    workflow.add_node("onboarding", onboarding_wrapper)

    def player_comparison_wrapper(state: AgentState) -> AgentState:
        # PlayerComparisonAgent wrapper
        try:
            input_dict: dict[str, Any] = {
                "user_email": state["user_email"],
                "league_id": state.get("league_id", ""),
                "messages": state["messages"]
            }
            result = player_comparison_agent.invoke(cast(Any, input_dict))
            return cast(AgentState, result)
        except Exception as e:
            logger.error(f"Error in player comparison agent: {e}", exc_info=True)
            # Mark flow as complete and route to clarification on error
            state["flow_complete"] = True
            state["needs_clarification"] = True
            return state

    workflow.add_node("player_comparison", player_comparison_wrapper)

    # Set entry point
    workflow.set_entry_point("controller")

    # Controller routes to first agent (or clarification/email/end)
    workflow.add_conditional_edges(
        "controller",
        route_to_next_agent,
        {
            "clarification": "clarification",
            "onboarding": "onboarding",
            "player_comparison": "player_comparison",
            "email": "email",
            "end": END,
        },
    )

    # After each agent, go to flow coordinator
    workflow.add_edge("onboarding", "flow_coordinator")
    workflow.add_edge("player_comparison", "flow_coordinator")

    # Clarification still ends (user needs to respond)
    workflow.add_edge("clarification", END)

    # Flow coordinator routes to next agent or email or end
    workflow.add_conditional_edges(
        "flow_coordinator",
        route_to_next_agent,
        {
            "onboarding": "onboarding",
            "player_comparison": "player_comparison",
            "email": "email",
            "end": END,
        },
    )

    # Email sends and ends
    workflow.add_edge("email", END)

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
