"""Controller agent that routes to appropriate sub-agents based on context."""

import logging
from typing import cast

from langchain_openai import ChatOpenAI

from agent.agent_state import AgentState, build_context, get_user_teams
from agent.routing_schemas import AgentType, RoutingDecision

logger = logging.getLogger(__name__)


def classify_user_intent(message: str) -> RoutingDecision:
    """
    Use LLM to classify user intent and determine agent routing.

    Args:
        message: The user's message content

    Returns:
        RoutingDecision with agent type, confidence score, and reasoning
    """
    classifier = ChatOpenAI(
        model="gpt-4o-mini", temperature=0
    ).with_structured_output(RoutingDecision)

    prompt = f"""Classify the user's intent and determine which agent should handle this request.

User message: {message}

Available agents:
- onboarding: Help users connect their Yahoo Fantasy teams, set up authentication, or add new teams
- player_comparison: Compare NHL players for fantasy hockey decisions (e.g., "who should I start?", "Player A vs Player B", "who's better?")
- general: General fantasy hockey questions, team stats, player information, or other assistance

Return the most appropriate agent and your confidence (0.0 to 1.0).

Guidelines:
- Use player_comparison for any question asking to compare or choose between players
- Use onboarding for account setup, team connection, or authentication issues
- Use general for informational queries, stats lookups, or unclear intents
"""

    result = cast(RoutingDecision, classifier.invoke([{"role": "user", "content": prompt}]))
    logger.info(
        f"LLM routing classification - Agent: {result.agent}, "
        f"Confidence: {result.confidence:.2f}, Reasoning: {result.reasoning}"
    )
    return result


def controller_node(state: AgentState) -> AgentState:
    """
    Controller node that determines routing based on user context.

    This node:
    1. Extracts the last user message
    2. Checks for comparison intent
    3. Checks if user has teams (if not, routes to onboarding)
    4. Builds context from message_id or infers from database
    5. Determines if clarification is needed
    6. Updates state with team information
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

    # Use LLM to classify user intent
    routing = classify_user_intent(message_content)

    # Route to player_comparison if classified with sufficient confidence
    if routing.agent == AgentType.PLAYER_COMPARISON and routing.confidence > 0.7:
        logger.info(
            f"Routing to player_comparison based on LLM classification "
            f"(confidence: {routing.confidence:.2f})"
        )
        state["needs_clarification"] = False
        state["route_to"] = "player_comparison"
        return state

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
        "player_comparison" if comparison intent detected
        "clarify" if clarification needed
        "onboarding" if no teams exist
        "continue" to proceed with normal flow
    """
    # Check for player comparison routing first
    if state.get("route_to") == "player_comparison":
        return "player_comparison"

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
