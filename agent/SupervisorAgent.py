"""Supervisor agent that coordinates sub-agents via tool calls."""

import os
from typing import Any, Literal, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.checkpointer import checkpointer
from agent.context_validator import validate_context
from agent.prompts.assemble import assemble_system_prompt
from agent.subagents.available import available_players
from agent.subagents.trade import trade
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from module.logger import get_logger
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.notifications.manage_notifications import manage_notifications
from tools.yahoo.onboard_user_team import onboard_user_team

END_NODE: Literal["__end__"] = "__end__"

logger = get_logger(__name__)


def create_supervisor_agent(system_prompt: str):
    """Create a new supervisor agent instance.

    Args:
        system_prompt: The fully assembled system prompt string.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        raise ValueError("OPENAI_API_KEY environment variable not set")

    from agent.memory_store import get_memory_store

    search_past_conversations = create_search_past_conversations_tool(get_memory_store())

    tools = [
        trade,
        available_players,
        onboard_user_team,
        search_past_conversations,
        manage_notifications,
    ]

    return create_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=tools,
        middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        state_schema=AgentState,  # type: ignore[arg-type]
    )


def _validate(state: AgentState):
    """Run context validation and return the result."""
    from agent.memory_store import get_memory_store

    return validate_context(state, get_memory_store())


def _add_error_response(state: AgentState, error_message: str) -> None:
    """Add an error message as an AIMessage to state messages."""
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=error_message))
    state["messages"] = messages
    state["response"] = error_message


def _invoke_supervisor(
    state: AgentState, user_email: str
) -> Command[Literal["response", "__end__"]]:
    """Invoke the supervisor agent and return the appropriate command."""
    try:
        validation_result = _validate(state)

        if validation_result.league_id:
            state["league_id"] = validation_result.league_id
        if validation_result.team_id:
            state["team_id"] = validation_result.team_id

        channel = state.get("channel", "email")
        system_prompt = assemble_system_prompt(validation_result, channel, user_email)

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
                    return Command(goto="response", update=state)

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
) -> Command[Literal["response", "__end__"]]:
    """Supervisor node that routes user requests to appropriate sub-agents."""
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

    return _invoke_supervisor(state, user_email)
