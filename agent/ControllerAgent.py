"""Controller agent that routes to appropriate sub-agents based on context."""

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
from agent.routing_schemas import AgentFlowDecision, AgentType
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.yahoo.get_roster import get_roster

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)

# System prompt for the controller agent
CONTROLLER_SYSTEM_PROMPT = """You are a helpful fantasy hockey assistant controller. Your role is to:

1. Understand what the user is asking for
2. Use your tools to gather information when needed (e.g., fetch their roster)
3. Either answer the user's question directly OR determine which specialized agent should handle it

When you have enough information to answer the user directly, respond with the answer.

When the user needs specialized help, indicate in your response which agent should handle it:
- Use [ROUTE:onboarding] for account setup, team connection, or authentication issues
- Use [ROUTE:player_comparison] for comparing players or "who should I start?" questions

The user's email and team context will be provided in system messages.
"""

# Database setup for checkpointer
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Create the controller agent with tools
if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

controller_agent = create_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[get_roster],
    middleware=[handle_tool_errors],
    system_prompt=SystemMessage(content=CONTROLLER_SYSTEM_PROMPT),
    checkpointer=checkpointer,
)


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

Available agents:
- onboarding: Help users connect their Yahoo Fantasy teams, set up authentication, or add new teams
- player_comparison: Compare NHL players for fantasy hockey decisions (e.g., "who should I start?", "Player A vs Player B", "who's better?")

Note: If the user has no teams connected, use the onboarding agent only.
Note: If the user is simply asking about their roster (e.g., "who's on my team?"), return an EMPTY flow - the controller can handle this directly.
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
    4. If flow is empty, runs the controller agent to handle directly with tools
    5. Otherwise routes to the appropriate sub-agent
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

    # Determine agent flow using LLM
    try:
        flow_decision = determine_agent_flow(
            message_content, state["has_teams"], user_email
        )
        agent_flow = [agent.value for agent in flow_decision.agent_flow]

        # Validate flow length
        from agent.routing_schemas import MAX_FLOW_LENGTH

        if len(agent_flow) > MAX_FLOW_LENGTH:
            logger.error(
                f"Flow length {len(agent_flow)} exceeds maximum {MAX_FLOW_LENGTH}. "
                "Truncating to max length."
            )
            agent_flow = agent_flow[:MAX_FLOW_LENGTH]

        # Handle empty flow - controller handles directly with tools
        if not agent_flow:
            logger.info("Empty agent flow - controller will handle directly with tools")
            return _handle_with_controller_agent(state, user_email, message_content)

        # Initialize flow tracking in state
        state["agent_flow"] = agent_flow
        state["current_agent_index"] = 0
        state["flow_complete"] = False
        state["flow_reasoning"] = flow_decision.reasoning

        logger.info(f"Initialized flow: {state['agent_flow']}")

    except Exception as e:
        logger.error(f"Error determining agent flow: {e}", exc_info=True)
        state["agent_flow"] = []
        state["current_agent_index"] = 0
        state["flow_complete"] = True
        state["needs_clarification"] = True
        return Command(goto="clarification", update=state)

    # Route to next agent in flow
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
    return Command(
        goto=cast(
            Literal["onboarding", "player_comparison", "clarification", "email"],
            next_agent,
        ),
        update=state,
    )


def _handle_with_controller_agent(
    state: AgentState, user_email: str | None, message_content: str
) -> Command[Literal["onboarding", "player_comparison", "clarification", "email", "__end__"]]:
    """
    Use the controller agent with tools to handle the request directly.

    Returns a Command to either end (if handled) or route to a sub-agent.
    """
    try:
        # Build context message for the agent
        context_parts = [f"User email: {user_email}"]
        if state.get("league_id"):
            context_parts.append(f"League ID: {state['league_id']}")
        if state.get("team_id"):
            context_parts.append(f"Team ID: {state['team_id']}")
        if state.get("user_teams"):
            teams_info = ", ".join(
                f"{t['team_name']} ({t['league_name']})" for t in state["user_teams"]
            )
            context_parts.append(f"User's teams: {teams_info}")

        context_msg = SystemMessage(content="\n".join(context_parts))

        # Invoke the controller agent
        input_dict: dict[str, Any] = {
            "messages": [context_msg, *list(state.get("messages", []))],
        }
        result = controller_agent.invoke(cast(Any, input_dict))

        # Extract the response
        if isinstance(result, dict) and "messages" in result:
            result_messages = result["messages"]
            if result_messages:
                last_msg = result_messages[-1]
                if isinstance(last_msg, AIMessage):
                    response_content = str(last_msg.content)

                    # Check if agent wants to route to a sub-agent
                    if "[ROUTE:onboarding]" in response_content:
                        state["agent_flow"] = ["onboarding"]
                        state["current_agent_index"] = 0
                        state["flow_complete"] = False
                        return Command(goto="onboarding", update=state)
                    elif "[ROUTE:player_comparison]" in response_content:
                        state["agent_flow"] = ["player_comparison"]
                        state["current_agent_index"] = 0
                        state["flow_complete"] = False
                        return Command(goto="player_comparison", update=state)

                    # Agent handled it directly - set response and go to email
                    state["response"] = response_content
                    state["messages"] = result_messages
                    state["flow_complete"] = True
                    return Command(goto="email", update=state)

    except Exception as e:
        logger.error(f"Error in controller agent: {e}", exc_info=True)
        state["needs_clarification"] = True
        state["response"] = "I encountered an error processing your request. Could you please try again?"
        return Command(goto="clarification", update=state)

    # Fallback - ask for clarification
    state["needs_clarification"] = True
    return Command(goto="clarification", update=state)


def clarification_node(state: AgentState) -> Command[Literal["__end__"]]:
    """
    Node that returns clarification message to user and ends the flow.
    User must respond before the flow can continue.
    """
    if not state.get("response"):
        state["response"] = "I need more information. Which team are you asking about?"

    return Command(goto=END_NODE, update=state)
