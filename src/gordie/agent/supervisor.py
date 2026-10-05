from typing import Any, Literal, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from gordie.agent.agent_state import AgentState
from gordie.agent.checkpointer import get_checkpointer
from gordie.agent.prompts.assemble import assemble_system_prompt
from gordie.agent.subagents.available import available_players
from gordie.agent.subagents.statistician import statistician
from gordie.agent.subagents.trade import trade
from gordie.middleware.sport_tool_filter import sport_tool_filter
from gordie.middleware.state_logger import StateLoggingMiddleware
from gordie.middleware.tool_call_error_wrapper import handle_tool_errors
from gordie.module.llm import make_llm
from gordie.module.logger import get_logger
from gordie.runtime import current_runtime
from gordie.tools.hockey.stats.query_stats_db import query_hockey_stats_db
from gordie.tools.memory.search_past_conversations import create_search_past_conversations_tool
from gordie.tools.yahoo.onboard_user_team import onboard_user_team

END_NODE: Literal["__end__"] = "__end__"

logger = get_logger(__name__)


def create_supervisor_agent(system_prompt: str):
    from gordie.agent.memory_store import get_memory_store, is_memory_search_enabled

    search_past_conversations = create_search_past_conversations_tool(
        get_memory_store(),
        enabled=is_memory_search_enabled(),
    )

    tools = [
        trade,
        available_players,
        statistician,
        query_hockey_stats_db,
        onboard_user_team,
        search_past_conversations,
    ]

    tools.extend(current_runtime().plugins.extra_tools)

    return create_agent(
        model=make_llm(temperature=0),
        tools=tools,
        middleware=[StateLoggingMiddleware("supervisor"), sport_tool_filter, handle_tool_errors],
        system_prompt=system_prompt,
        checkpointer=get_checkpointer(),
        state_schema=AgentState,  # type: ignore[arg-type]
    )


def _add_error_response(state: AgentState, error_message: str) -> None:
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=error_message))
    state["messages"] = messages
    state["response"] = error_message


def _invoke_access_response(
    state: AgentState,
) -> Command[Literal["data_quality", "response", "__end__"]]:
    response = state.get("access_context") or "This action is unavailable."
    return Command(
        goto=END_NODE,
        update={"response": response, "messages": [AIMessage(content=response)]},
    )


def _invoke_supervisor(
    state: AgentState,
) -> Command[Literal["data_quality", "response", "__end__"]]:
    try:
        system_prompt = assemble_system_prompt(state)

        input_state: dict[str, Any] = dict(state)
        input_state["messages"] = list(state.get("messages", []))

        thread_id = state.get("thread_id") or "default"
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("Invoking supervisor agent with sub-agent tools...")

        agent = create_supervisor_agent(system_prompt)
        result = agent.invoke(cast(Any, input_state), cast(RunnableConfig, cast(object, config)))

        if isinstance(result, dict) and "messages" in result:
            result_messages = result["messages"]
            if result_messages:
                last_msg = result_messages[-1]
                if isinstance(last_msg, AIMessage):
                    response_content = str(last_msg.content)
                    state["response"] = response_content
                    state["messages"] = result_messages
                    logger.info(f"Supervisor response: {response_content[:200]}...")
                    return Command(goto="data_quality", update=state)

        _add_error_response(state, "I couldn't process your request. Could you please rephrase?")
        return Command(goto="response", update=state)

    except Exception as e:
        logger.error(f"Error in supervisor agent: {e}", exc_info=True)
        _add_error_response(
            state, "I encountered an error processing your request. Could you please try again?"
        )
        return Command(goto="response", update=state)


def supervisor_node(
    state: AgentState,
) -> Command[Literal["data_quality", "response", "__end__"]]:
    messages = state.get("messages", [])
    user_id = state.get("user_id") or ""

    if not messages or not user_id:
        logger.warning(f"Missing {'messages' if not messages else 'user_id'} in state")
        return Command(goto=END_NODE, update=state)

    last_message = messages[-1]
    message_content = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )

    logger.info(f"Supervisor processing: {message_content}...")

    if state.get("context_status") == "access_blocked":
        return _invoke_access_response(state)

    return _invoke_supervisor(state)
