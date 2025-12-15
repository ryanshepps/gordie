"""Controller agent that routes to appropriate sub-agents based on context."""

import logging
from typing import cast

from agent.agent_state import AgentState, build_context, get_user_teams

logger = logging.getLogger(__name__)


def controller_node(state: AgentState) -> AgentState:
    """
    Controller node that determines routing based on user context.

    This node:
    1. Extracts the last user message
    2. Checks if user has teams (if not, routes to onboarding)
    3. Builds context from message_id or infers from database
    4. Determines if clarification is needed
    5. Updates state with team information
    """
    messages = state.get("messages", [])
    user_email = state.get("user_email")

    if not messages:
        logger.warning("No messages in state")
        return state

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

    logger.info(f"Controller processing message: {message_content[:100]}...")
    logger.info(f"Team context: {team_context}")

    # Get user's teams
    user_teams = get_user_teams(user_email)
    state["user_teams"] = user_teams
    state["has_teams"] = len(user_teams) > 0

    # If user has no teams, route directly to onboarding
    if not state["has_teams"]:
        logger.info("User has no teams - routing to onboarding agent")
        # Don't set needs_clarification - we want to go straight to onboarding
        state["needs_clarification"] = False
        return state

    # Build context from team_context or infer from message
    if team_context:
        context = build_context(team_context, message_content, user_email)

        if context.get("needs_clarification"):
            # Need to ask user for clarification
            state["needs_clarification"] = True
            state["response"] = cast(str | None, context.get("clarification_message"))
            logger.info("Clarification needed - asking user to specify team")
        else:
            # Context successfully built/inferred
            state["game_key"] = cast(str | None, context.get("game_key"))
            state["league_id"] = cast(str | None, context.get("league_id"))
            state["team_id"] = cast(str | None, context.get("team_id"))
            state["needs_clarification"] = False
            state["team_inference"] = cast(dict[str, str] | None, context.get("team_inference"))

            if state["team_inference"]:
                logger.info(f"Inferred team: {state['team_inference']}")
    else:
        # No team_context provided - will need to infer or ask
        if not user_teams:
            state["needs_clarification"] = True
            state["response"] = (
                "I couldn't find any teams associated with your account. Would you like to onboard a team first?"
            )
        else:
            # Try to infer from context in downstream nodes
            state["needs_clarification"] = False

    return state


def should_ask_for_clarification(state: AgentState) -> str:
    """
    Routing function to determine next step.

    Returns:
        "clarify" if clarification needed
        "onboarding" if no teams exist
        "continue" to proceed with normal flow
    """
    # If user has no teams, always route to onboarding
    if not state.get("has_teams"):
        return "onboarding"

    # Otherwise check if clarification is needed
    if state.get("needs_clarification"):
        return "clarify"

    return "continue"


def clarification_node(state: AgentState) -> AgentState:
    """
    Node that returns clarification message to user.
    """
    # The response should already be set by controller
    if not state.get("response"):
        state["response"] = "I need more information. Which team are you asking about?"

    return state
