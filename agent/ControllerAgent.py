"""Controller agent that routes to appropriate sub-agents based on context."""

import logging
from typing import Literal, cast

from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agent.agent_state import AgentState, build_context, get_user_teams
from agent.routing_schemas import AgentFlowDecision, AgentType, RoutingDecision

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

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

Return the most appropriate agent and your confidence (0.0 to 1.0).

Guidelines:
- Use player_comparison for any question asking to compare or choose between players
- Use onboarding for account setup, team connection, or authentication issues
- If the request is unclear or doesn't match these capabilities, return an empty flow (the system will ask for clarification)
"""

    result = cast(RoutingDecision, classifier.invoke([{"role": "user", "content": prompt}]))
    logger.info(
        f"LLM routing classification - Agent: {result.agent}, "
        f"Confidence: {result.confidence:.2f}, Reasoning: {result.reasoning}"
    )
    return result


def determine_agent_flow(
    message: str, has_teams: bool, user_email: str | None
) -> AgentFlowDecision:
    """
    Use LLM to determine the complete agent flow for handling this request.

    Args:
        message: The user's message content
        has_teams: Whether the user has any teams connected
        user_email: The user's email address

    Returns:
        AgentFlowDecision with ordered agent sequence, confidence, and reasoning
    """
    flow_classifier = ChatOpenAI(
        model="gpt-4o-mini", temperature=0
    ).with_structured_output(AgentFlowDecision)

    prompt = f"""Determine the complete flow of agents needed to handle this user request.

User message: {message}
User has teams connected: {has_teams}
User email available: {user_email is not None}

Note: If the user has no teams connected, use the onboarding agent only.
"""

    result = cast(
        AgentFlowDecision,
        flow_classifier.invoke([{"role": "user", "content": prompt}]),
    )
    logger.info(
        f"LLM flow determination - Flow: {[agent.value for agent in result.agent_flow]}, "
        f"Confidence: {result.confidence:.2f}, Reasoning: {result.reasoning}"
    )
    return result


def controller_node(
    state: AgentState,
) -> Command[Literal["onboarding", "player_comparison", "clarification", "email", "__end__"]]:
    """
    Controller node that determines routing based on user context.

    This node:
    1. Extracts the last user message
    2. Gets user's teams to check if they have any
    3. Calls determine_agent_flow() to get the complete flow
    4. Initializes flow tracking in state
    5. Builds context from team_context or infers from database
    6. Determines if clarification is needed
    7. Returns a Command to route to the appropriate next node
    """
    messages = state.get("messages", [])
    user_email = state.get("user_email")

    if not messages:
        logger.warning("No messages in state")
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

    logger.info(f"Controller processing message: {message_content[:100]}...")
    logger.info(f"Team context: {team_context}")

    # Get user's teams
    user_teams = get_user_teams(user_email)
    state["user_teams"] = user_teams
    state["has_teams"] = len(user_teams) > 0

    # Determine agent flow using LLM
    try:
        flow_decision = determine_agent_flow(
            message_content, state["has_teams"], user_email
        )

        # Convert enum values to strings
        agent_flow = [agent.value for agent in flow_decision.agent_flow]

        # Validate flow length
        from agent.routing_schemas import MAX_FLOW_LENGTH

        if len(agent_flow) > MAX_FLOW_LENGTH:
            logger.error(
                f"Flow length {len(agent_flow)} exceeds maximum {MAX_FLOW_LENGTH}. "
                "Truncating to max length."
            )
            agent_flow = agent_flow[:MAX_FLOW_LENGTH]

        # Handle empty flow - route to clarification
        if not agent_flow:
            logger.warning("LLM returned empty agent flow. Routing to clarification.")
            state["agent_flow"] = []
            state["current_agent_index"] = 0
            state["flow_complete"] = True
            state["flow_reasoning"] = flow_decision.reasoning
            state["needs_clarification"] = True
            return Command(goto="clarification", update=state)

        # Initialize flow tracking in state
        state["agent_flow"] = agent_flow
        state["current_agent_index"] = 0
        state["flow_complete"] = False
        state["flow_reasoning"] = flow_decision.reasoning

        logger.info(f"Initialized flow: {state['agent_flow']}")

    except Exception as e:
        logger.error(f"Error determining agent flow: {e}", exc_info=True)
        # Route to clarification on error
        state["agent_flow"] = []
        state["current_agent_index"] = 0
        state["flow_complete"] = True
        state["needs_clarification"] = True
        return Command(goto="clarification", update=state)

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
            state["team_inference"] = cast(
                dict[str, str] | None, context.get("team_inference")
            )

            if state["team_inference"]:
                logger.info(f"Inferred team: {state['team_inference']}")
    else:
        # No team_context provided - will need to infer or ask
        # If user has no teams AND the flow is not onboarding, ask for clarification
        # The onboarding agent is designed to handle users without teams
        if not user_teams and agent_flow != ["onboarding"]:
            state["needs_clarification"] = True
            state["response"] = (
                "I couldn't find any teams associated with your account. Would you like to onboard a team first?"
            )
        else:
            # Try to infer from context in downstream nodes, or let onboarding handle it
            state["needs_clarification"] = False

    # Determine routing based on state
    if state.get("needs_clarification"):
        return Command(goto="clarification", update=state)

    if state.get("flow_complete"):
        return Command(goto="email", update=state)

    # Route to next agent in flow
    agent_flow = state.get("agent_flow", [])
    current_index = state.get("current_agent_index", 0)

    if not agent_flow or current_index >= len(agent_flow):
        logger.warning("Empty or exhausted agent flow, routing to end")
        return Command(goto=END_NODE, update=state)

    next_agent = agent_flow[current_index]

    # Validate agent name
    valid_agents = {agent.value for agent in AgentType}
    if next_agent not in valid_agents:
        logger.error(
            f"Invalid agent name '{next_agent}' in flow at index {current_index}. "
            f"Valid agents: {valid_agents}. Routing to end."
        )
        return Command(goto=END_NODE, update=state)

    logger.info(
        f"Routing to next agent: {next_agent} (index {current_index}/{len(agent_flow) - 1})"
    )
    # Cast to satisfy type checker - we've already validated next_agent is valid
    return Command(
        goto=cast(
            Literal["onboarding", "player_comparison", "clarification", "email"],
            next_agent,
        ),
        update=state,
    )


def clarification_node(state: AgentState) -> Command[Literal["__end__"]]:
    """
    Node that returns clarification message to user and ends the flow.
    User must respond before the flow can continue.
    """
    # The response should already be set by controller
    if not state.get("response"):
        state["response"] = "I need more information. Which team are you asking about?"

    return Command(goto=END_NODE, update=state)
