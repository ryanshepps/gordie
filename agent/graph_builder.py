from langgraph.graph import StateGraph

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from agent.context_node import context_node
from agent.data_quality_node import data_quality_node
from agent.response_node import response_node
from agent.SupervisorAgent import supervisor_node
from agent.voice_rewrite_node import voice_rewrite_node


def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("context", context_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_quality", data_quality_node)
    workflow.add_node("voice_rewrite", voice_rewrite_node)
    workflow.add_node("response", response_node)

    workflow.set_entry_point("context")
    workflow.add_edge("context", "supervisor")

    return workflow.compile(checkpointer=checkpointer)


agent = build_agent_graph()
