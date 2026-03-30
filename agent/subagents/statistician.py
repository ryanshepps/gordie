"""Statistician sub-agent for rigorous statistical analysis of fantasy sports data."""

from typing import Annotated, cast

from langchain.tools import InjectedState, tool

from agent.context_types import Sport
from agent.prompts.sport_context import get_sport_context
from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from module.logger import get_logger
from tools.compute.execute_python import execute_python
from tools.stats.query_stats_db import query_stats_db
from tools.yahoo_stats.yahoo_league import yahoo_league
from tools.yahoo_stats.yahoo_player import yahoo_player
from tools.yahoo_stats.yahoo_roster import yahoo_roster
from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

logger = get_logger(__name__)


_statistician_task = """
You are a fantasy sports statistician. You answer ANY statistical question using real data and \
rigorous computation. You never approximate or guess — you fetch data and compute.

## Workflow

1. Understand the statistical question being asked.
2. Determine what data is needed. Fetch it via Yahoo tools (and query_stats_db for advanced stats).
3. Write and execute Python code via execute_python to compute the statistics.
4. Present findings with specific numbers, context, and interpretation.

## Data Fetching Rules

- Always call yahoo_league with method "get_league_info" first to get current_week before \
iterating over weeks.
- Always call yahoo_league with method "get_league_teams" to get all team IDs before doing \
league-wide analysis.
- For weekly data across the season, loop from week 1 to current_week.
- Use yahoo_scoring for matchup scores, standings, and team-level stats.
- Use yahoo_roster for per-player stats on a specific team's roster.
- Use yahoo_player for individual player lookups by player_key.
- Use yahoo_league for draft results, transactions, settings, and league metadata.
- Use query_stats_db for advanced stats (sport-specific metrics provided in context).

## Statistical Capabilities

You can compute any of the following (and more):
- Descriptive statistics: mean, median, std dev, variance, percentiles, range, IQR
- Z-scores and position-adjusted normalization
- Correlation analysis: Pearson and Spearman between stat categories
- Linear regression and trend analysis (week-over-week performance)
- Luck analysis: actual wins vs expected wins (median-based)
- Consistency metrics: coefficient of variation, weekly standard deviation
- Draft value analysis: pick cost vs production, ROI
- Composite scoring: weighted multi-factor rankings
- Distribution analysis: skewness, kurtosis, normality tests
- Comparative analysis: across teams, positions, or time periods

## Example Patterns

- "Most consistent team?" -> Fetch weekly scores via yahoo_scoring (scoreboard for each week), \
compute std dev of weekly scores per team. Lower std dev = more consistent.
- "Which starter is dragging me down?" -> Fetch roster stats via yahoo_roster, compute \
position-adjusted z-scores. Negative z-scores indicate underperformance.
- "Am I lucky or good?" -> Fetch weekly scores + standings. Compare actual W-L to median-based \
expected W-L (win if your score > league median that week).
- "Biggest draft bust?" -> Fetch draft results via yahoo_league + season production via \
yahoo_roster. Compare pick value vs actual value.
- "Scoring trend for each team?" -> Fetch weekly scores, run linear regression per team. \
Positive slope = improving, negative = declining.

## Computation Rules

- Always use execute_python for computations beyond basic arithmetic.
- Pass fetched data as data_json to execute_python, then compute in code.
- Print results from execute_python — that's how output is returned.
- If code errors, read the error message and fix the code.
- Present results with interpretation (e.g., "z-score of -1.8 means 1.8 standard deviations \
below the position average — bottom 4% of the distribution").

User: {user_email} | League: {league_id} | Team: {team_id}
"""

agent = create_subagent(
    name="statistician",
    system_prompt=_statistician_task,
    tools=[
        yahoo_scoring,
        yahoo_roster,
        yahoo_player,
        yahoo_league,
        execute_python,
        query_stats_db,
    ],
    response_format=None,
)


@tool
def statistician(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """Perform statistical analysis on fantasy league data.

    Use this tool for questions involving:
    - Consistency analysis (weekly scoring variance, coefficient of variation)
    - Z-scores and normalization (position-adjusted performance)
    - Correlation and regression (stat relationships, trends over time)
    - Luck analysis (actual vs expected wins)
    - Draft efficiency (pick value vs production, ROI)
    - Distribution analysis (skewness, kurtosis, percentiles)
    - Comparative statistics across teams, players, or time periods
    - Any question requiring mathematical computation on league data

    Args:
        request: The user's statistical question in natural language.
        user_email: The email address of the user.
        league_id: The ID of the fantasy league.
        team_id: The ID of the user's team.
        state: The agent state (injected).

    Returns:
        Statistical analysis with specific numbers, context, and interpretation.
    """
    logger.info(f"Statistician sub-agent invoked with request: {request}")

    sport = cast(Sport | None, state.get("sport")) if state else None
    result = invoke_subagent(
        agent=agent,
        request=request,
        context_parts=[
            f"User email: {user_email}",
            f"League ID: {league_id}",
            f"Team ID: {team_id}",
            get_sport_context(sport),
        ],
    )

    response = extract_response(
        result,
        fallback_message="I ran into an error while performing the statistical analysis.",
    )

    logger.info(f"Statistician sub-agent response: {response}")
    return response
