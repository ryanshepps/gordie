import os
from typing import Any, Literal, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from agent.prompts.assemble import assemble_system_prompt
from agent.subagents.available import available_players
from agent.subagents.statistician import statistician
from agent.subagents.trade import trade
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from module.logger import get_logger
from tools.billing.generate_checkout_link import generate_checkout_link
from tools.billing.generate_portal_link import generate_portal_link
from tools.billing.get_subscription_status import get_subscription_status
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.notifications.manage_notifications import manage_notifications
from tools.stats.query_stats_db import query_stats_db
from tools.yahoo.onboard_user_team import onboard_user_team

END_NODE: Literal["__end__"] = "__end__"

logger = get_logger(__name__)


def create_supervisor_agent(system_prompt: str):
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        raise ValueError("OPENAI_API_KEY environment variable not set")

    from agent.memory_store import get_memory_store

    search_past_conversations = create_search_past_conversations_tool(get_memory_store())

    tools = [
        trade,
        available_players,
        statistician,
        query_stats_db,
        onboard_user_team,
        search_past_conversations,
        manage_notifications,
        get_subscription_status,
        generate_checkout_link,
        generate_portal_link,
    ]

    return create_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=tools,
        middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        state_schema=AgentState,  # type: ignore[arg-type]
    )


def _add_error_response(state: AgentState, error_message: str) -> None:
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=error_message))
    state["messages"] = messages
    state["response"] = error_message


def _invoke_billing_response(
    state: AgentState, user_email: str
) -> Command[Literal["data_quality", "response", "__end__"]]:
    try:
        system_prompt = assemble_system_prompt(state)

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        user_messages = []
        for m in state.get("messages", []):
            if isinstance(m, dict):
                user_messages.append({"role": "user", "content": str(m.get("content", ""))})
            elif hasattr(m, "type") and m.type == "human":
                user_messages.append({"role": "user", "content": str(m.content)})
        messages = [{"role": "system", "content": system_prompt}, *user_messages]

        response = llm.invoke(messages)
        response_content = str(response.content)

        state["response"] = response_content
        ai_msg = AIMessage(content=response_content)
        state["messages"] = [*list(state.get("messages", [])), ai_msg]

        return Command(goto="data_quality", update=state)
    except Exception as e:
        logger.error(f"Error in billing response: {e}", exc_info=True)
        _add_error_response(
            state, "I encountered an error processing your request. Could you please try again?"
        )
        return Command(goto="response", update=state)


def _invoke_supervisor(
    state: AgentState, user_email: str
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
    user_email = state.get("user_email") or ""

    if not messages or not user_email:
        logger.warning(f"Missing {'messages' if not messages else 'user_email'} in state")
        return Command(goto=END_NODE, update=state)

    last_message = messages[-1]
    message_content = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )

    logger.info(f"Supervisor processing: {message_content}...")

    if state.get("context_status") == "billing_blocked":
        return _invoke_billing_response(state, user_email)

    return _invoke_supervisor(state, user_email)
