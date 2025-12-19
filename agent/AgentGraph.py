import logging
import os
import sqlite3
from typing import Any, Literal, cast

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.types import Command

from agent.agent_state import AgentState

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

# Type alias for valid agent destinations
AgentDestination = Literal["onboarding", "player_comparison", "clarification", "email", "__end__"]

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


def get_next_destination(state: AgentState) -> str:
    """
    Determine the next destination after an agent completes.

    Increments the current_agent_index and returns the next agent
    or "email" if the flow is complete.
    """
    agent_flow = state.get("agent_flow", [])
    current_index = state.get("current_agent_index", 0)

    # Increment index for next agent
    next_index = current_index + 1
    state["current_agent_index"] = next_index

    if next_index >= len(agent_flow):
        state["flow_complete"] = True
        logger.info(f"Flow complete. Processed {next_index} agents.")
        return "email"

    next_agent = agent_flow[next_index]
    logger.info(f"Next agent in flow: {next_agent} (index {next_index}/{len(agent_flow) - 1})")
    return next_agent


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

    return Command(goto=END_NODE, update=state)


def build_agent_graph():
    """Build and return the agent graph with controller and sub-agents.

    Uses Command-based routing instead of conditional edges for dynamic
    agent handoffs. Each node returns a Command that specifies both
    state updates and the next node to execute.
    """
    from agent.ControllerAgent import (
        clarification_node,
        controller_node,
    )
    from agent.OnboardingAgent import agent as onboarding_agent
    from agent.PlayerComparisonAgent import agent as player_comparison_agent

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes - no edges needed, Commands handle routing
    workflow.add_node("controller", controller_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("email", email_node)

    def onboarding_wrapper(
        state: AgentState,
    ) -> Command[AgentDestination]:
        """Wrapper for onboarding agent that returns a Command for routing."""
        try:
            input_dict: dict[str, Any] = {
                "user_email": state["user_email"],
                "messages": state["messages"],
            }
            result = onboarding_agent.invoke(cast(Any, input_dict))
            # Merge result into state
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in state:
                        state[key] = value  # type: ignore[literal-required]
        except Exception as e:
            logger.error(f"Error in onboarding agent: {e}", exc_info=True)
            state["flow_complete"] = True
            state["needs_clarification"] = True
            return Command(goto="clarification", update=state)

        # Determine next destination and route
        next_dest = get_next_destination(state)
        logger.info(f"Onboarding complete, routing to: {next_dest}")
        # Cast to satisfy type checker - get_next_destination returns valid destinations
        return Command(goto=cast(AgentDestination, next_dest), update=state)

    workflow.add_node("onboarding", onboarding_wrapper)

    def player_comparison_wrapper(
        state: AgentState,
    ) -> Command[AgentDestination]:
        """Wrapper for player comparison agent that returns a Command for routing."""
        try:
            input_dict: dict[str, Any] = {
                "user_email": state["user_email"],
                "league_id": state.get("league_id", ""),
                "messages": state["messages"],
            }
            result = player_comparison_agent.invoke(cast(Any, input_dict))
            # Merge result into state
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in state:
                        state[key] = value  # type: ignore[literal-required]
        except Exception as e:
            logger.error(f"Error in player comparison agent: {e}", exc_info=True)
            state["flow_complete"] = True
            state["needs_clarification"] = True
            return Command(goto="clarification", update=state)

        # Determine next destination and route
        next_dest = get_next_destination(state)
        logger.info(f"Player comparison complete, routing to: {next_dest}")
        # Cast to satisfy type checker - get_next_destination returns valid destinations
        return Command(goto=cast(AgentDestination, next_dest), update=state)

    workflow.add_node("player_comparison", player_comparison_wrapper)

    # Set entry point - Commands handle all routing from here
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
