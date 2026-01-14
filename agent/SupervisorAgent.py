"""Supervisor agent that coordinates sub-agents via tool calls."""

import logging
import os
import sqlite3
from typing import Any, Literal, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.context_validator import validate_and_build_system_message
from agent.subagents.available import available_players
from agent.subagents.trade import trade
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.yahoo.onboard_user_team import onboard_user_team

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)

# Persona for user-facing communication
PERSONA = """
TONE:
You are Gordie. You're tough, crack a few jokes but you're not rude.
You use short sentences, slang and metaphors according to the sport you are
currently assisting with. Use professional language. Act as if you were a real
fantasy league assistant, and a client of yours is coming to you for advice.

AUDIENCE:
Your clients are NOT technologically savvy. Do not include technical jargon,
complex language or ask for IDs.

IMPORTANT:
Never reveal internal technical details such as the tools you are calling, the
processes you are running, or the technology you are using. This is not useful
to the user, and you want to be useful for the user.
"""

# System prompt for the supervisor agent
SUPERVISOR_SYSTEM_PROMPT = """Complete the user's request by using the available tools to help them.

## CRITICAL RULES:

1. **REWRITE ALL TOOL RESPONSES TO MATCH YOUR PERSONA**: Never pass through tool or sub-agent \
responses directly. Completely rewrite them in your voice while preserving URLs, links, and data.
2. **NEVER OMIT OAUTH URLs**: If a tool returns an 'oauth_url' you MUST include the exact \
URL in your response to the user. Never paraphrase or omit URLs.
3. **ONBOARDING IS DETERMINISTIC**: When the system message provides team selection instructions, \
simply follow them. Present OAuth links or team lists exactly as specified. When the user selects \
a team, call onboard_user_team with the correct parameters from the system message.
4. Use search_past_conversations proactively when it would help provide better context-aware advice.
"""

# Database setup for checkpointer
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)


def create_supervisor_agent():
    """Create a new supervisor agent instance."""
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Import from memory_store module to avoid circular import with graph_builder
    from agent.memory_store import get_memory_store

    # Create the search tool with access to the memory store
    search_past_conversations = create_search_past_conversations_tool(get_memory_store())

    return create_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=[
            trade,
            available_players,
            onboard_user_team,
            search_past_conversations,
        ],
        middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
        system_prompt=SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        checkpointer=checkpointer,
        state_schema=AgentState,  # type: ignore[arg-type]
    )


def _build_context_message(
    state: AgentState, user_email: str
) -> tuple[SystemMessage, str | None, str | None]:
    """
    Build the context system message for the supervisor agent using context validator.

    Returns:
        Tuple of (SystemMessage, league_id, team_id)
    """
    from agent.memory_store import get_memory_store

    # Run context validation
    result = validate_and_build_system_message(state, get_memory_store())

    # Build the full context message
    parts = [f"User email: {user_email}", "", result.system_message]

    if result.league_id:
        parts.append(f"\nLeague ID: {result.league_id}")
    if result.team_id:
        parts.append(f"Team ID: {result.team_id}")

    return SystemMessage(content="\n".join(parts)), result.league_id, result.team_id


def _prepare_input_state(state: AgentState, context_msg: SystemMessage) -> dict[str, Any]:
    """Prepare input state with system messages for the supervisor agent."""
    input_state: dict[str, Any] = dict(state)
    system_messages: list[SystemMessage] = []

    system_messages.append(SystemMessage(content=PERSONA))
    system_messages.append(context_msg)

    input_state["messages"] = [*system_messages, *list(state.get("messages", []))]
    return input_state


def _add_error_response(state: AgentState, error_message: str) -> None:
    """Add an error message as an AIMessage to state messages."""
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=error_message))
    state["messages"] = messages
    state["response"] = error_message


def _invoke_supervisor(
    state: AgentState, user_email: str
) -> Command[Literal["email", "__end__"]]:
    """Invoke the supervisor agent and return the appropriate command."""
    try:
        context_msg, league_id, team_id = _build_context_message(state, user_email)

        # Update state with validated context
        if league_id:
            state["league_id"] = league_id
        if team_id:
            state["team_id"] = team_id

        input_state = _prepare_input_state(state, context_msg)

        # Build config with thread_id for checkpointer
        thread_id = state.get("thread_id") or "default"
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("Invoking supervisor agent with sub-agent tools...")
        result = create_supervisor_agent().invoke(
            cast(Any, input_state), cast(RunnableConfig, cast(object, config))
        )

        # Extract the response
        if isinstance(result, dict) and "messages" in result:
            result_messages = result["messages"]
            if result_messages:
                last_msg = result_messages[-1]
                if isinstance(last_msg, AIMessage):
                    response_content = str(last_msg.content)
                    state["response"] = response_content
                    state["messages"] = result_messages
                    logger.info(f"Supervisor response: {response_content[:200]}...")
                    return Command(goto="email", update=state)

        # No valid response
        _add_error_response(state, "I couldn't process your request. Could you please rephrase?")
        return Command(goto="email", update=state)

    except Exception as e:
        logger.error(f"Error in supervisor agent: {e}", exc_info=True)
        _add_error_response(
            state, "I encountered an error processing your request. Could you please try again?"
        )
        return Command(goto="email", update=state)


def supervisor_node(
    state: AgentState,
) -> Command[Literal["email", "__end__"]]:
    """Supervisor node that routes user requests to appropriate sub-agents."""
    messages = state.get("messages", [])
    user_email = state.get("user_email") or ""

    # Early exit for invalid state
    if not messages or not user_email:
        logger.warning(f"Missing {'messages' if not messages else 'user_email'} in state")
        return Command(goto=END_NODE, update=state)

    # Extract message content and team context
    last_message = messages[-1]
    message_content = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )

    logger.info(f"Supervisor processing: {message_content}...")

    # Invoke supervisor agent
    return _invoke_supervisor(state, user_email)
