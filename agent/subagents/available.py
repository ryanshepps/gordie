"""Available players sub-agent for finding streaming/pickup opportunities."""

from typing import Annotated, Any

from langchain.tools import InjectedState, tool

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from module.logger import get_logger
from tools.available.search_available_players import search_available_players
from tools.stats.get_player_line_info import get_player_line_info
from tools.stats.get_player_schedule import get_player_schedule
from tools.stats.query_stats_db import query_stats_db
from tools.yahoo.get_player_yahoo_info import get_player_yahoo_info
from tools.yahoo.get_team_roster import get_team_roster

logger = get_logger(__name__)


_available_players_task = """
You help users find available players to pick up in fantasy hockey.

## Approach

1. Understand the user's question
2. Use the appropriate tools to gather data
3. Analyze and present findings with specific numbers

**For "who should I pick up" questions:**
- Search for top available players
- Get stats for promising candidates
- Compare to user's droppable players if relevant

**For player comparisons ("X or Y"):**
- Get stats for both players
- Get schedule for both
- Compare directly with specific metrics

**For stat-based queries ("most goals last week"):**
- Use appropriate sort and sort_type parameters
- Present results with the requested stats

**For streaming decisions:**
- Factor in schedule (more games = more opportunity)
- Consider recent performance (lastweek sort)

## Key Stats to Reference

When making recommendations, cite specific stats:
- **Points/Goals**: Raw production
- **xGoals vs Goals**: Positive GAE = overperforming (may regress), Negative = underperforming (may improve)
- **Fenwick%**: Possession quality (>52% is good, >55% is elite)
- **TOI**: Ice time shows trust from coach
- **Line number**: 1st line = best linemates/opportunities
- **Schedule**: More games this week = more chances to score

## Accuracy Rules

- Only present stats returned by tool calls. Never fill in numbers from memory.
- If no players match the user's criteria, say so. Do not loosen the criteria or
  reinterpret the question to produce a longer list.
- Give exactly one final answer. Do not present a correct answer and then override
  it with a weaker reinterpretation.

User: {user_email} | League: {league_id} | Team: {team_id}
"""

agent = create_subagent(
    name="available",
    system_prompt=_available_players_task,
    tools=[
        search_available_players,
        query_stats_db,
        get_player_schedule,
        get_player_line_info,
        get_player_yahoo_info,
        get_team_roster,
    ],
    response_format=None,  # Flexible responses based on query type
)


@tool
def available_players(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
    state: Annotated[dict[str, Any], InjectedState] | None = None,
):
    """Analyze available players and recommend pickups for fantasy hockey.

    Use this tool for:
    - Finding available player pickups (free agents + waivers)
    - Comparing specific available players ("should I pick up X or Y")
    - Stat-based queries ("who has the most goals this month")
    - Schedule-based streaming decisions
    - Evaluating potential drops from user's roster

    Args:
        request: The user's request in natural language
        user_email: The email address of the user
        league_id: The ID of the fantasy league
        team_id: The ID of the team
        state: The agent state (injected)

    Returns:
        Analysis and recommendations based on the user's query
    """
    logger.info(f"Available players sub-agent invoked with request: {request}")

    result = invoke_subagent(
        agent=agent,
        request=request,
        context_parts=[
            f"User email: {user_email}",
            f"League ID: {league_id}",
            f"Team ID: {team_id}",
        ],
    )

    response = extract_response(
        result,
        fallback_message="I ran into an error while processing your available players request.",
    )

    logger.info(f"Available players sub-agent response: {response}")
    return response
