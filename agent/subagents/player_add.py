"""Player add sub-agent for finding available players, evaluating pickups, and roster decisions."""

import logging
from typing import Annotated, Any

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from agent.subagents.player_comparison import compare_players
from tools.player_comparison.calculate_fantasy_points import calculate_fantasy_points
from tools.player_comparison.compare_players_comprehensive import compare_players_comprehensive
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_player_stats import get_player_stats
from tools.yahoo.filter_players_by_nhl_team import filter_players_by_nhl_team
from tools.yahoo.get_available_players import get_available_players
from tools.yahoo.get_league_players import get_league_players
from tools.yahoo.get_league_teams import get_league_teams
from tools.yahoo.get_roster import get_roster
from tools.yahoo.get_team_roster import get_team_roster

logger = logging.getLogger(__name__)

_player_add_task = """
You help users find players to add, trade, or drop from their fantasy hockey roster.

CRITICAL RULES:
1. You MUST call tools to get real data. NEVER give generic advice.
2. ALWAYS call get_roster FIRST to see the user's current players.
3. ALWAYS call get_available_players or filter_players_by_nhl_team to find replacement options.
4. Your final response must include SPECIFIC player names with real stats.

TOOLS:

get_roster(user_email, league_id, team_id)
- Get user's current roster. CALL THIS FIRST.

get_available_players(user_email, league_id, status, position, count)
- Find free agents (status="FA") or waiver players (status="W") or all (status="A")

filter_players_by_nhl_team(user_email, league_id, nhl_teams, mode, status, position, count)
- Find players NOT on specific NHL teams: mode="exclude", nhl_teams=["TB", "FLA"]
- Find players ON specific NHL teams: mode="include"

get_league_teams(user_email, league_id)
- Get all fantasy teams and their managers (for proposing trades)

get_team_roster(user_email, league_id, team_id)
- Get any team's roster to scout for trade targets

get_league_players(user_email, league_id, status, position, search, count, sort)
- Search players. status="T" for taken/rostered players only.

compare_players(request, user_email, league_id)
- Compare players using stats and fantasy scoring

WORKFLOW FOR "I have too many [Team] players, help me trade":

1. Call get_roster → identify players from that NHL team
2. Call filter_players_by_nhl_team with mode="exclude" and nhl_teams=[team] → find available replacements NOT on that team
3. Call compare_players → compare your players vs available options
4. If good waiver options exist → recommend specific pickups with who to drop
5. If no good waivers:
   a. Call get_league_teams → get all fantasy teams and managers
   b. Call get_league_players with status="T" → find owned players at same positions
   c. Call compare_players → find fair trade matches
   d. Recommend: "Trade [Your Player] to [Manager Name]'s team for [Their Player]"

RESPONSE FORMAT:
- List the specific players to trade/drop with their current fantasy points
- List the specific replacement players with their stats
- For trades, include the fantasy team manager name
- Explain WHY each move makes sense based on the stats

User email: {user_email}
League ID: {league_id}
Team ID: {team_id}
"""

_agent = create_subagent(
    name="player_add",
    system_prompt=_player_add_task,
    tools=[
        get_available_players,
        get_league_players,
        get_roster,
        get_league_teams,
        get_team_roster,
        filter_players_by_nhl_team,
        compare_players,
        fuzzy_resolve_nhl_api_player_ids,
        get_player_stats,
        calculate_fantasy_points,
        compare_players_comprehensive,
    ],
)


class _PlayerAddInput(BaseModel):
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
    state: Annotated[dict[str, Any], InjectedState] | None = Field(default=None)


@tool(args_schema=_PlayerAddInput)
def handle_player_add(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
    state: Annotated[dict[str, Any], InjectedState] | None = None,
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
    if not league_id:
        return "I need to know which league you're asking about. Please connect your Yahoo Fantasy team first using the onboarding process."

    if not team_id:
        return "I need to know which team you're managing. Please connect your Yahoo Fantasy team first using the onboarding process."

    logger.info(f"[handle_player_add] Processing request for {user_email} (league={league_id}, team={team_id}): {request[:100]}...")
    logger.info(f"[handle_player_add] Injected state: {state}")
    logger.info(f"[handle_player_add] State keys: {state.keys() if state else 'None'}")

    persona = state.get("persona", "") if state else ""
    logger.info(f"[handle_player_add] Persona found: {bool(persona)}")

    result = invoke_subagent(
        agent=_agent,
        request=request,
        state=state,
        context_parts=[
            f"User email: {user_email}",
            f"League ID: {league_id}",
            f"Team ID: {team_id}",
        ],
    )

    response = extract_response(
        result,
        fallback_message="I encountered an issue processing your player add request. Please try again.",
    )
    logger.info(f"[handle_player_add] Response: {response[:200]}...")
    return response
