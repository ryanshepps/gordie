"""Tool wrapper for the player comparison sub-agent."""

from typing import Annotated, Any, cast

from langchain.tools import InjectedState, tool

from module.logger import get_logger

logger = get_logger(__name__)


@tool
def compare_players(
    request: str,
    user_email: str,
    league_id: str = "",
    state: Annotated[dict[str, Any], InjectedState] | None = None,
) -> str:
    """Compare NHL players for fantasy hockey decisions.

    Use this when the user wants to:
    - Compare two or more players
    - Decide who to start
    - Evaluate player performance
    - Get player recommendations
    - Answer "Player A vs Player B" questions
    - Get advice on which player is better

    Args:
        request: The user's player comparison request in natural language
        user_email: The user's email address
        league_id: The Yahoo league ID for fantasy point calculations

    Returns:
        The player comparison agent's analysis and recommendation
    """
    # Import here to avoid circular imports
    from langchain_core.messages import SystemMessage

    from agent.PlayerComparisonAgent import agent as player_comparison_agent

    logger.info(f"[compare_players] Processing request for {user_email}: {request[:100]}...")

    # Get persona from state if available
    persona = state.get("persona", "") if state else ""

    # Inject persona and user context as system messages
    system_messages = []

    if persona:
        system_messages.append(SystemMessage(content=persona))

    context_parts = [f"User email: {user_email}"]
    if league_id:
        context_parts.append(f"League ID: {league_id}")

    user_context_msg = SystemMessage(content="\n".join(context_parts))
    system_messages.append(user_context_msg)

    # Build input state with required messages field
    input_state = {
        "messages": [*system_messages, {"role": "user", "content": request}],
    }

    result = player_comparison_agent.invoke(cast(Any, input_state))

    # Extract the last AI message content
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        response = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        logger.info(f"[compare_players] Response: {response[:200]}...")
        return response

    return "I encountered an issue processing your player comparison request. Please try again."
