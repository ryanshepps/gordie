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
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.memory.search_past_conversations import create_search_past_conversations_tool
from tools.subagents import compare_players, handle_onboarding, handle_player_add
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

# Supervisor agent singleton - lazily initialized
_supervisor_agent = None


def get_supervisor_agent():
    """Get or create the supervisor agent singleton."""
    global _supervisor_agent
    if _supervisor_agent is None:
        if not os.environ.get("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY environment variable not set")
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Import from memory_store module to avoid circular import with graph_builder
        from agent.memory_store import get_memory_store

        # Create the search tool with access to the memory store
        search_past_conversations = create_search_past_conversations_tool(get_memory_store())

        _supervisor_agent = create_agent(
            model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
            tools=[get_roster, compare_players, handle_player_add, handle_onboarding, search_past_conversations],
            middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
            system_prompt=SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            checkpointer=checkpointer,
            state_schema=AgentState,  # type: ignore[arg-type]
        )
    return _supervisor_agent


def supervisor_node(
    state: AgentState,
) -> Command[Literal["clarification", "email", "__end__"]]:
    """
    Supervisor node that handles user requests via sub-agent tools.

    This node:
    1. Extracts the last user message and user context
    2. Builds context (user email, league ID, team ID)
    3. Invokes the supervisor agent which will call appropriate sub-agent tools
    4. Routes to email node with the response
    """
    messages = state.get("messages", [])
    user_email = state.get("user_email") or ""

    if not messages:
        logger.warning("No messages in state")
        return Command(goto=END_NODE, update=state)

    if not user_email:
        logger.warning("No user_email in state")
        return Command(goto=END_NODE, update=state)

    # Get the last user message
    last_message = messages[-1]
    message_content = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )
    team_context = (
        last_message.get("team_context")
        if isinstance(last_message, dict)
        else getattr(last_message, "team_context", None)
    )

    logger.info(f"Supervisor processing message: {message_content[:100]}...")
    logger.info(f"Team context: {team_context}")

    # Get user's teams
    user_teams = get_user_teams(user_email)
    state["user_teams"] = user_teams
    state["has_teams"] = len(user_teams) > 0

    # Build context from team_context or infer from message
    if team_context:
        context = build_context(team_context, message_content, user_email)

        if context.get("needs_clarification"):
            state["needs_clarification"] = True
            state["response"] = cast(str | None, context.get("clarification_message"))
            logger.info("Clarification needed - asking user to specify team")
            return Command(goto="clarification", update=state)
        else:
            state["game_key"] = cast(str | None, context.get("game_key"))
            state["league_id"] = cast(str | None, context.get("league_id"))
            state["team_id"] = cast(str | None, context.get("team_id"))
            state["needs_clarification"] = False
            state["team_inference"] = cast(
                dict[str, str] | None, context.get("team_inference")
            )
    else:
        # No team_context - check if user has teams
        if not user_teams:
            # No teams, will likely need onboarding
            state["needs_clarification"] = False
        elif len(user_teams) == 1:
            # Single team - use it automatically
            team = user_teams[0]
            state["game_key"] = team.get("game_key")
            state["league_id"] = team.get("league_id")
            state["team_id"] = team.get("team_id")
            state["needs_clarification"] = False

    # Invoke the supervisor agent with sub-agent tools
    try:
        # Build context message for the agent
        context_parts = [f"User email: {user_email}"]
        league_id = state.get("league_id")
        team_id = state.get("team_id")
        user_teams_list = state.get("user_teams")
        if league_id:
            context_parts.append(f"League ID: {league_id}")
        if team_id:
            context_parts.append(f"Team ID: {team_id}")
        if user_teams_list:
            teams_info = ", ".join(
                f"{t['team_name']} ({t['league_name']})" for t in user_teams_list
            )
            context_parts.append(f"User's teams: {teams_info}")
        if not state.get("has_teams"):
            context_parts.append("Note: User has no teams connected yet. Use handle_onboarding if they need to set up.")

        context_msg = SystemMessage(content="\n".join(context_parts))

        # Invoke the supervisor agent with full state
        # Create a copy of state and update messages with context
        input_state: dict[str, Any] = dict(state)

        # Build system messages list - include persona if available
        system_messages = []
        persona = state.get("persona", "")
        if persona:
            system_messages.append(SystemMessage(content=persona))
            logger.info("[SupervisorAgent] Persona injected into supervisor")
        system_messages.append(context_msg)

        input_state["messages"] = [*system_messages, *list(state.get("messages", []))]

        logger.info("Invoking supervisor agent with sub-agent tools...")
        result = get_supervisor_agent().invoke(cast(Any, input_state))

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

        # No valid response - ask for clarification
        state["needs_clarification"] = True
        state["response"] = "I couldn't process your request. Could you please rephrase?"
        return Command(goto="clarification", update=state)

    except Exception as e:
        logger.error(f"Error in supervisor agent: {e}", exc_info=True)
        state["needs_clarification"] = True
        state["response"] = "I encountered an error processing your request. Could you please try again?"
        return Command(goto="clarification", update=state)


def clarification_node(state: AgentState) -> Command[Literal["__end__"]]:
    """
    Node that returns clarification message to user and ends the flow.
    User must respond before the flow can continue.
    """
    if not state.get("response"):
        state["response"] = "I need more information. Which team are you asking about?"

    return Command(goto=END_NODE, update=state)
