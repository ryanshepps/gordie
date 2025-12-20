"""Tool wrapper for the player add sub-agent."""

from langchain.agents.middleware.types import _InputAgentState
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)


class PlayerAddInput(BaseModel):
    """Input schema for the player add tool."""

    request: str = Field(
        description="The user's request about finding or adding players (e.g., 'Who is available at center?', 'Should I pick up Player X?')"
    )
    user_email: str = Field(
        description="The user's email address for authentication"
    )
    league_id: str = Field(
        description="The Yahoo Fantasy league ID (numeric string, e.g., '26455'). Required to search for available players in the league."
    )
    team_id: str = Field(
        description="The Yahoo Fantasy team ID (numeric string, e.g., '7'). Required to compare against the user's current roster."
    )


@tool(args_schema=PlayerAddInput)
def handle_player_add(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
) -> str:
    """Find and evaluate players to add to your fantasy hockey roster.

    Use this when the user wants to:
    - Find available players (free agents or waivers)
    - Search for a specific player to see if they're available
    - Get recommendations on who to pick up
    - Evaluate whether to add a specific player
    - Find the best available player at a position
    - Compare available players against their current roster

    IMPORTANT: This tool requires both league_id and team_id to function.
    If the user has no teams connected, use handle_onboarding first.

    Args:
        request: The user's request about finding or adding players
        user_email: The user's email address
        league_id: The Yahoo Fantasy league ID (required)
        team_id: The Yahoo Fantasy team ID (required)

    Returns:
        The player add agent's analysis and recommendations
    """
    # Import here to avoid circular imports
    from langchain_core.messages import SystemMessage

    from agent.PlayerAddAgent import agent as player_add_agent

    # Validate required fields
    if not league_id:
        return "I need to know which league you're asking about. Please connect your Yahoo Fantasy team first using the onboarding process."

    if not team_id:
        return "I need to know which team you're managing. Please connect your Yahoo Fantasy team first using the onboarding process."

    logger.info(f"[handle_player_add] Processing request for {user_email} (league={league_id}, team={team_id}): {request[:100]}...")

    # Inject user context as a system message
    context_parts = [
        f"User email: {user_email}",
        f"League ID: {league_id}",
        f"Team ID: {team_id}",
    ]

    user_context_msg = SystemMessage(content="\n".join(context_parts))

    # Build input state with required messages field
    input_state: _InputAgentState = {
        "messages": [user_context_msg, {"role": "user", "content": request}],
    }

    result = player_add_agent.invoke(input_state)

    # Extract the last AI message content
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        response = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        logger.info(f"[handle_player_add] Response: {response[:200]}...")
        return response

    return "I encountered an issue processing your player add request. Please try again."
