"""Agent graph for the fantasy hockey assistant.

Uses a simplified supervisor pattern where sub-agents are invoked as tools
rather than separate graph nodes. This provides deterministic routing
through explicit tool calls.
"""

import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

from agent.agent_state import AgentState
from agent.email_node import email_node
from agent.SupervisorAgent import clarification_node, supervisor_node


def build_agent_graph():
    """Build and return the simplified agent graph.

    The graph has 3 nodes:
    - supervisor: Handles requests via sub-agent tools
    - clarification: Asks user for more information when needed
    - email: Sends the response to the user

    Sub-agents (onboarding, player_comparison) are invoked as tools
    by the supervisor rather than being separate graph nodes.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("email", email_node)

    workflow.set_entry_point("supervisor")

    # Setup persistent checkpointer
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return workflow.compile(checkpointer=checkpointer)


agent = build_agent_graph()
