"""Trade sub-agent for finding players to trade for"""

from typing import Annotated, Any

from langchain.tools import InjectedState, tool

from agent.response_models import TradeResponse
from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from module.logger import get_logger
from tools.player_comparison.calculate_undervalued_score import (
    calculate_undervalued_score,
)
from tools.stats.query_stats_db import query_stats_db
from tools.yahoo.find_similar_ranked_players import find_similar_ranked_players
from tools.yahoo.get_league_teams import get_league_teams
from tools.yahoo.get_team_roster import get_team_roster

logger = get_logger(__name__)


_player_assessment_task = """
Find REALISTIC trade targets with detailed statistical analysis and trade pitches.

## CRITICAL: Realistic Trade Targets

NEVER recommend players who are OBVIOUSLY BETTER than the subject player:
- Do NOT suggest elite superstars (rank 1-20) as trade targets for mid-tier players
- Do NOT suggest players ranked 10+ spots higher - they won't be traded 1-for-1
- Target players ranked SIMILARLY OR WORSE but with BETTER UNDERLYING STATS

The goal is finding UNDERVALUED players - players who LOOK worse (lower rank, fewer points)
but have BETTER advanced stats indicating they'll improve:
- Negative Goals Above Expected (shooting unlucky, will regress UP)
- Strong Fenwick/Corsi % (good possession, opportunities will come)
- High ice time / top line deployment (getting opportunities)
- Favorable schedule (more games = more chances)

## Workflow

1. Determine trade direction using get_team_roster:
   - Player on user's team → "trading_away" (sell to opponents)
   - Player not on team → "trading_for" (acquire from opponents)

2. Find trade targets using find_similar_ranked_players:
   - Find players ranked in a similar range to the subject player
   - For "trading_away": look for players with WORSE rank but BETTER underlying stats
   - For "trading_for": look for similarly-ranked players with better upside indicators

3. Get stats for ALL players using query_stats_db, then calculate_undervalued_score:
   - Use query_stats_db with SQL to fetch player stats from the skaters table
   - Pass the fetched stats to calculate_undervalued_score for Yahoo rank, schedule, and scoring
   - IMPORTANT: Each player gets an undervalued_score and undervalued_reasons

4. FILTER trade targets based on realism:
   - EXCLUDE any player ranked 10+ spots better than subject player
   - EXCLUDE elite players (rank 1-20) unless subject is also elite
   - PRIORITIZE players with HIGHER undervalued_score than subject player
   - PRIORITIZE players with NEGATIVE goals_above_expected (will regress UP)

5. Use undervalued_score to prioritize targets:
   - Score > 5: Highly undervalued - STRONG BUY, prioritize these targets
   - Score 3-5: Moderately undervalued - good trade target
   - Score 0-3: Fairly valued
   - Score < 0: OVERVALUED - avoid acquiring, good to trade away

6. Build pitches based on direction:

   Trading away: You're SELLING the subject player to acquire better underlying talent.
   Target players who are ranked WORSE but have BETTER advanced stats (higher undervalued_score,
   negative GAE, strong Fenwick%, good TOI). Explain to the trade partner why YOUR player
   looks good on the surface while acquiring someone with more upside.

   Each pitch must include 5+ specific stat values comparing both players AND explain WHY
   the target is obtainable (they look bad on surface but have hidden value).

Return TradeResponse with complete player_stats for subject + all targets, and trade_targets
with detailed pitches and reasoning. The summary MUST cite specific advanced stats (xGoals, Fenwick%, schedule, line info) - summaries using only rank will be rejected.

User: {user_email} | League: {league_id} | Team: {team_id}
"""

agent = create_subagent(
    name="trade",
    system_prompt=_player_assessment_task,
    tools=[
        get_team_roster,
        get_league_teams,
        query_stats_db,
        calculate_undervalued_score,
        find_similar_ranked_players,
    ],
    response_format=TradeResponse,
)


@tool
def trade(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
    state: Annotated[dict[str, Any], InjectedState] | None = None,
):
    """Analyze trade opportunities and find trade targets using advanced hockey statistics.

    Use this tool for:
    - Trade suggestions and finding trade targets on other teams
    - Player comparisons for trade decisions (uses xGoals, Fenwick%, Corsi%, TOI)
    - Identifying undervalued players based on advanced analytics
    - Finding trade partners when user has roster imbalances
    - Questions like "who should I trade", "trade targets", "help me trade"

    This tool performs comprehensive analysis including MoneyPuck advanced stats,
    schedule analysis, linemate information, and undervalued player scoring.

    Args:
        request (str): The user's trade request in natural language.
        user_email (str): The email address of the user.
        league_id (str): The ID of the fantasy league.
        team_id (str): The ID of the team.
        state: The state of the agent. Defaults to None.

    Returns:
        str: Detailed trade analysis with specific player recommendations and statistical comparisons.
    """
    logger.info(f"Trade sub-agent invoked with request: {request}")

    result = invoke_subagent(
        agent=agent,
        request=request,
        context_parts=[
            f"User email: {user_email}",
            f"League ID: {league_id}",
            f"Team ID: {team_id}",
        ],
    )

    # Check for structured response first
    structured = result.get("structured_response")
    if structured:
        logger.info(f"Trade sub-agent structured response: {structured}")
        return str(structured)

    response = extract_response(
        result, fallback_message="I ran into an error while processing your trade request."
    )

    logger.info(f"Trade sub-agent response: {response}")
    return response
