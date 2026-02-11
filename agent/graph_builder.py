"""Agent graph for the fantasy hockey assistant.

Uses a simplified supervisor pattern where sub-agents are invoked as tools
rather than separate graph nodes. This provides deterministic routing
through explicit tool calls.
"""

from langgraph.graph import StateGraph

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from agent.response_node import response_node
from agent.SupervisorAgent import supervisor_node


def build_agent_graph():
    """Build and return the simplified agent graph.

    The graph has 2 nodes:
    - supervisor: Handles requests via sub-agent tools
    - response: Dispatches the response to the appropriate channel (email, SMS, web)

    Sub-agents (onboarding, player_comparison) are invoked as tools
    by the supervisor rather than being separate graph nodes.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("response", response_node)

    workflow.set_entry_point("supervisor")

    return workflow.compile(checkpointer=checkpointer)


agent = build_agent_graph()
