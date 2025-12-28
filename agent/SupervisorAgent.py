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

from agent.agent_state import AgentState, build_context, get_user_teams
from agent.context_validator import validate_and_build_system_message
from agent.subagents.trade import trade
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.player_comparison.compare_players_comprehensive import compare_players_comprehensive
from tools.player_comparison.get_comprehensive_player_stats import get_comprehensive_player_stats
from tools.yahoo.get_available_players import get_available_players
from tools.yahoo.get_roster import get_roster
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
5. **ALWAYS USE TOOLS FOR PLAYER ANALYSIS**: When asked about dropping/adding/analyzing a player, \
you MUST call get_comprehensive_player_stats to get their actual stats before giving advice. \
Never give vague responses - provide specific data-driven recommendations.

The user's email and team context will be provided in system messages.
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
            get_roster,
            trade,
            onboard_user_team,
            search_past_conversations,
            # Player analysis and comparison tools for roster decisions
            get_comprehensive_player_stats,
            compare_players_comprehensive,
            get_available_players,
        ],
        middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
        system_prompt=SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        checkpointer=checkpointer,
        state_schema=AgentState,  # type: ignore[arg-type]
    )


def _get_team_context(message: Any) -> Any:
    """Extract team_context from a message."""
    if isinstance(message, dict):
        return message.get("team_context")
    return getattr(message, "team_context", None)


def _resolve_team_context(
    state: AgentState, team_context: Any, message_content: str, user_email: str
) -> Command[Literal["clarification", "email", "__end__"]] | None:
    """
    Resolve team context and update state.

    Returns a Command if clarification is needed, otherwise None.
    """
    user_teams = get_user_teams(user_email)
    state["user_teams"] = user_teams

    if team_context:
        context = build_context(team_context, message_content, user_email)
        if context.get("needs_clarification"):
            state["response"] = cast(str | None, context.get("clarification_message"))
            logger.info("Clarification needed - asking user to specify team")
            return Command(goto="clarification", update=state)
        state.update(
            {
                "league_id": cast(str | None, context.get("league_id")),
                "team_id": cast(str | None, context.get("team_id")),
            }
        )
    elif len(user_teams) == 1:
        team = user_teams[0]
        state.update(
            {
                "league_id": team.get("league_id"),
                "team_id": team.get("team_id"),
            }
        )

    return None


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
    validation_message, league_id, team_id = validate_and_build_system_message(
        state, get_memory_store()
    )

    # Build the full context message
    parts = [f"User email: {user_email}", "", validation_message]

    if league_id:
        parts.append(f"\nLeague ID: {league_id}")
    if team_id:
        parts.append(f"Team ID: {team_id}")

    return SystemMessage(content="\n".join(parts)), league_id, team_id


def _prepare_input_state(state: AgentState, context_msg: SystemMessage) -> dict[str, Any]:
    """Prepare input state with system messages for the supervisor agent."""
    input_state: dict[str, Any] = dict(state)
    system_messages: list[SystemMessage] = []

    system_messages.append(SystemMessage(content=PERSONA))
    system_messages.append(context_msg)

    input_state["messages"] = [*system_messages, *list(state.get("messages", []))]
    return input_state


def _invoke_supervisor(
    state: AgentState, user_email: str
) -> Command[Literal["clarification", "email", "__end__"]]:
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
        state["response"] = "I couldn't process your request. Could you please rephrase?"
        return Command(goto="clarification", update=state)

    except Exception as e:
        logger.error(f"Error in supervisor agent: {e}", exc_info=True)
        state["response"] = (
            "I encountered an error processing your request. Could you please try again?"
        )
        return Command(goto="clarification", update=state)


def supervisor_node(
    state: AgentState,
) -> Command[Literal["clarification", "email", "__end__"]]:
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
    team_context = _get_team_context(last_message)

    logger.info(f"Supervisor processing: {message_content[:100]}...")

    # Resolve team context (may return early with clarification)
    if cmd := _resolve_team_context(state, team_context, message_content, user_email):
        return cmd

    # Invoke supervisor agent
    return _invoke_supervisor(state, user_email)


def clarification_node(state: AgentState) -> Command[Literal["__end__"]]:
    """
    Node that returns clarification message to user and ends the flow.
    User must respond before the flow can continue.
    """
    if not state.get("response"):
        state["response"] = "I need more information. Which team are you asking about?"

    return Command(goto=END_NODE, update=state)
