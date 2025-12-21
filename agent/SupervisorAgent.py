"""Supervisor agent that coordinates sub-agents via tool calls."""

import logging
import os
import sqlite3
from typing import Any, Literal, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent.agent_state import AgentState, build_context, get_user_teams
from agent.subagents import compare_players, handle_onboarding, handle_player_add
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.yahoo.get_roster import get_roster

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)

# System prompt for the supervisor agent
SUPERVISOR_SYSTEM_PROMPT = """You are a routing agent for a fantasy hockey assistant. Your ONLY job is to route requests to the correct sub-agent tool.

AVAILABLE TOOLS:

1. **handle_player_add** - USE THIS FOR:
   - Trade suggestions ("help me trade", "who should I trade", "trade targets")
   - Waiver/free agent questions ("who is available", "who should I pick up")
   - Roster imbalances ("too many players from X team")
   - Player add/drop decisions
   - ANY request that involves finding replacement players or making roster moves

2. **compare_players** - USE THIS FOR:
   - Direct player comparisons ("compare Player A vs Player B")
   - Start/sit decisions ("who should I start")
   - "Which player is better" questions

3. **handle_onboarding** - USE THIS FOR:
   - Account setup and Yahoo connection
   - First-time user setup
   - Returns JSON with 'status', 'message', and optionally 'oauth_url'
   - **IMPORTANT**: If 'oauth_url' is present in the response, you MUST include this exact URL in your message to the user. Never paraphrase or omit URLs.

4. **get_roster** - USE THIS FOR:
   - Simple roster queries ONLY ("who's on my team", "show my roster")
   - DO NOT use this for trades, waivers, or any decision-making

5. **search_past_conversations** - USE THIS FOR:
   - When the user references a previous conversation ("remember when...", "last time we talked about...")
   - When you want to check if similar advice was given before
   - When the user asks about a player they previously discussed
   - When the user can't find an old email and asks you to remind them
   - When providing context-aware advice that builds on previous discussions

CRITICAL RULES:

1. If the user mentions "trade", "waiver", "pick up", "add", "drop", "too many players from", or wants roster advice:
   → YOU MUST call handle_player_add. Do NOT just call get_roster and give generic advice.

2. The handle_player_add tool will:
   - Fetch the roster itself
   - Search for available players
   - Find trade targets on other teams
   - Compare players and give SPECIFIC recommendations with real data

3. YOU ARE NOT ALLOWED to give trade/waiver advice yourself. You MUST delegate to handle_player_add.

4. When you receive a response from a sub-agent tool, use that information to craft an appropriate response to the user. You may rephrase and adapt the message, but you MUST preserve any URLs, links, or specific data exactly as provided.

5. Use search_past_conversations proactively when it would help provide better context-aware advice.

The user's email and team context will be provided in system messages.
"""

# Database setup for checkpointer
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
)
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
        tools=[get_roster, compare_players, handle_player_add, handle_onboarding, search_past_conversations],
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
    state["has_teams"] = len(user_teams) > 0

    if team_context:
        context = build_context(team_context, message_content, user_email)
        if context.get("needs_clarification"):
            state["response"] = cast(str | None, context.get("clarification_message"))
            logger.info("Clarification needed - asking user to specify team")
            return Command(goto="clarification", update=state)
        state.update({
            "league_id": cast(str | None, context.get("league_id")),
            "team_id": cast(str | None, context.get("team_id")),
        })
    elif len(user_teams) == 1:
        team = user_teams[0]
        state.update({
            "league_id": team.get("league_id"),
            "team_id": team.get("team_id"),
        })

    return None


def _build_context_message(state: AgentState, user_email: str) -> SystemMessage:
    """Build the context system message for the supervisor agent."""
    parts = [f"User email: {user_email}"]

    if league_id := state.get("league_id"):
        parts.append(f"League ID: {league_id}")
    if team_id := state.get("team_id"):
        parts.append(f"Team ID: {team_id}")
    if user_teams := state.get("user_teams"):
        teams_info = ", ".join(
            f"{t['team_name']} ({t['league_name']})" for t in user_teams
        )
        parts.append(f"User's teams: {teams_info}")
    if not state.get("has_teams"):
        parts.append(
            "Note: User has no teams connected yet. "
            "Use handle_onboarding if they need to set up."
        )

    return SystemMessage(content="\n".join(parts))


def _prepare_input_state(
    state: AgentState, context_msg: SystemMessage
) -> dict[str, Any]:
    """Prepare input state with system messages for the supervisor agent."""
    input_state: dict[str, Any] = dict(state)
    system_messages: list[SystemMessage] = []

    if persona := state.get("persona", ""):
        system_messages.append(SystemMessage(content=persona))
        logger.info("[SupervisorAgent] Persona injected into supervisor")
    system_messages.append(context_msg)

    input_state["messages"] = [*system_messages, *list(state.get("messages", []))]
    return input_state


def _invoke_supervisor(
    state: AgentState, user_email: str
) -> Command[Literal["clarification", "email", "__end__"]]:
    """Invoke the supervisor agent and return the appropriate command."""
    try:
        context_msg = _build_context_message(state, user_email)
        input_state = _prepare_input_state(state, context_msg)

        logger.info("Invoking supervisor agent with sub-agent tools...")
        result = create_supervisor_agent().invoke(cast(Any, input_state))

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
