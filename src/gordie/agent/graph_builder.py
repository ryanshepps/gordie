from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from gordie.agent.agent_state import AgentState
from gordie.agent.checkpointer import get_checkpointer
from gordie.agent.context_node import context_node
from gordie.agent.data_quality_node import data_quality_node
from gordie.agent.response_node import make_response_node
from gordie.agent.supervisor import supervisor_node
from gordie.agent.voice_rewrite_node import make_voice_rewrite_node
from gordie.runtime import current_runtime


def build_agent_graph(graph_checkpointer: BaseCheckpointSaver[str] | None = None):
    workflow = StateGraph(AgentState)

    workflow.add_node("context", context_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_quality", data_quality_node)
    workflow.add_node("voice_rewrite", make_voice_rewrite_node())  # pyright: ignore[reportArgumentType]
    workflow.add_node("response", make_response_node())  # pyright: ignore[reportArgumentType]

    workflow.set_entry_point("context")
    workflow.add_edge("context", "supervisor")

    return workflow.compile(
        checkpointer=graph_checkpointer if graph_checkpointer is not None else get_checkpointer()
    )  # pyright: ignore[reportArgumentType]


def get_agent() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    return current_runtime().resource("graph", build_agent_graph)
