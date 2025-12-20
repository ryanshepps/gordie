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
from tools.subagents import compare_players, handle_onboarding, handle_player_add
from tools.yahoo.get_roster import get_roster

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)

# System prompt for the supervisor agent
SUPERVISOR_SYSTEM_PROMPT = """You are a helpful fantasy hockey assistant.

You have access to specialized tools to help users:

1. **compare_players**: Use this for ANY question involving player comparisons, including:
   - "Compare Player A vs Player B"
   - "Who should I start?"
   - "Which player is better?"
   - "Player recommendations"
   - Any question about choosing between players

2. **handle_player_add**: Use this for finding and evaluating players to add, including:
   - "Who is available on waivers?"
   - "Who should I pick up?"
   - "Is Player X available?"
   - "Find me a center to add"
   - "Who are the best free agents?"
   - "Should I pick up Player Y?"
   - Any question about adding players, free agents, or waiver claims

3. **handle_onboarding**: Use this for account and team setup, including:
   - Connecting Yahoo Fantasy account
   - Adding a new team to track
   - Authentication issues
   - First-time user setup

4. **get_roster**: Use this to fetch the user's current roster when they ask:
   - "Who's on my team?"
   - "Show me my roster"
   - General roster queries

IMPORTANT RULES:
- When a user asks to compare players or wants advice on who to start, ALWAYS use the compare_players tool.
- When a user asks about available players, waivers, free agents, or who to pick up, ALWAYS use handle_player_add tool.
- When a user needs to set up their account or connect a team, ALWAYS use handle_onboarding tool.
- Pass the full user request to the sub-agent tools so they have complete context.
- After a sub-agent tool returns, summarize or present the results to the user.

The user's email and team context will be provided in system messages.
"""

# Database setup for checkpointer
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Create the supervisor agent with sub-agent tools
if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

supervisor_agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[get_roster, compare_players, handle_player_add, handle_onboarding],
    middleware=[StateLoggingMiddleware("supervisor"), handle_tool_errors],
    system_prompt=SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
    checkpointer=checkpointer,
    state_schema=AgentState,  # type: ignore[arg-type]
)


def controller_node(
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
        input_state["messages"] = [context_msg, *list(state.get("messages", []))]

        logger.info("Invoking supervisor agent with sub-agent tools...")
        result = supervisor_agent.invoke(cast(Any, input_state))

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
