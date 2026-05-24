from langgraph.graph import StateGraph

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from agent.context_node import context_node
from agent.data_quality_node import data_quality_node
from agent.response_node import make_response_node
from agent.SupervisorAgent import supervisor_node
from agent.voice_rewrite_node import make_voice_rewrite_node
from server.adapters import build_registry


def build_agent_graph(graph_checkpointer: object | None = checkpointer):
    registry = build_registry()
    workflow = StateGraph(AgentState)

    workflow.add_node("context", context_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_quality", data_quality_node)
    workflow.add_node("voice_rewrite", make_voice_rewrite_node(registry))  # pyright: ignore[reportArgumentType]
    workflow.add_node("response", make_response_node())  # pyright: ignore[reportArgumentType]

    workflow.set_entry_point("context")
    workflow.add_edge("context", "supervisor")

    return workflow.compile(checkpointer=graph_checkpointer)  # pyright: ignore[reportArgumentType]


agent = build_agent_graph()
