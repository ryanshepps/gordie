"""Player comparison sub-agent for fantasy hockey analysis."""

import logging
from typing import Annotated, Any

from langchain.tools import InjectedState, tool

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from tools.player_comparison.calculate_fantasy_points import calculate_fantasy_points
from tools.player_comparison.compare_players_comprehensive import compare_players_comprehensive
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_player_stats import get_player_stats

logger = logging.getLogger(__name__)

_player_comparison_task = """
Task: Compare NHL players to help the user make informed fantasy hockey decisions.

Comparison Process:
1. If the user provides player names (e.g., "McDavid" or "Draisaitl"), use fuzzy_resolve_nhl_api_player_ids to get their NHL API player IDs
2. Use get_player_stats to fetch statistics for each player (requires player IDs)
3. Use calculate_fantasy_points for fantasy scoring
4. Use compare_players_comprehensive for analysis
5. Present a clear recommendation with supporting data

Important: Always resolve player names to IDs first before fetching stats. The get_player_stats tool requires numeric player IDs, not names.

User email: {user_email}
League ID: {league_id}
"""

_agent = create_subagent(
    name="player_comparison",
    system_prompt=_player_comparison_task,
    tools=[fuzzy_resolve_nhl_api_player_ids, get_player_stats, calculate_fantasy_points, compare_players_comprehensive],
)


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
    logger.info(f"[compare_players] Processing request for {user_email}: {request[:100]}...")

    context_parts = [f"User email: {user_email}"]
    if league_id:
        context_parts.append(f"League ID: {league_id}")

    result = invoke_subagent(
        agent=_agent,
        request=request,
        state=state,
        context_parts=context_parts,
    )

    response = extract_response(
        result,
        fallback_message="I encountered an issue processing your player comparison request. Please try again.",
    )
    logger.info(f"[compare_players] Response: {response[:200]}...")
    return response
