"""Trade sub-agent for finding players to trade for"""

from typing import Annotated, Any

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field, field_validator, model_validator

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from module.logger import get_logger
from tools.player_comparison.get_comprehensive_player_stats import (
    get_comprehensive_player_stats,
)
from tools.yahoo.find_similar_ranked_players import find_similar_ranked_players
from tools.yahoo.get_league_teams import get_league_teams
from tools.yahoo.get_team_roster import get_team_roster

logger = get_logger(__name__)


class Linemate(BaseModel):
    """A player's linemate information."""

    name: str = Field(description="Linemate's full name")
    position: str = Field(description="Linemate's position")
    shared_ice_time_pct: float = Field(
        description="Percentage of ice time shared with this linemate", ge=0, le=100
    )


class PlayerStats(BaseModel):
    """Comprehensive stats for a single player.

    These stats MUST come from get_comprehensive_player_stats - do not fabricate values.
    """

    name: str = Field(description="Player's full name")
    team: str = Field(description="Team abbreviation")
    position: str = Field(description="Player position (C, LW, RW, D)")

    # Yahoo fantasy data
    yahoo_rank: int | None = Field(default=None, description="Yahoo fantasy season rank")

    # MoneyPuck stats
    games_played: int = Field(description="Number of games played", ge=1)
    goals: int = Field(description="Goals scored", ge=0)
    assists: int = Field(description="Total assists", ge=0)
    points: int = Field(description="Total points", ge=0)
    toi_per_game: float = Field(
        description="Average time on ice per game in minutes - must be from MoneyPuck data",
        gt=0,
    )
    x_goals: float = Field(
        description="Expected goals from MoneyPuck - REQUIRED, cannot be 0 or fabricated",
        gt=0,
    )
    goals_above_expected: float = Field(description="Goals minus expected goals")
    fenwick_pct: float = Field(
        description="Fenwick percentage from MoneyPuck (typically 45-55)",
        gt=0,
        le=100,
    )
    corsi_pct: float = Field(
        description="Corsi percentage from MoneyPuck (typically 45-55)",
        gt=0,
        le=100,
    )
    points_per_game: float = Field(description="Points per game", ge=0)

    # Schedule data
    games_remaining_this_week: int | None = Field(
        default=None, description="Number of games remaining this fantasy week"
    )
    games_next_week: int | None = Field(
        default=None, description="Number of games next fantasy week"
    )

    # Line information
    estimated_line_number: int | None = Field(
        default=None, description="Estimated line number (1-4 for forwards, 1-3 for defense)"
    )
    primary_linemates: list[Linemate] = Field(
        default_factory=list, description="Primary linemates this player plays with"
    )

    # Undervalued analysis
    undervalued_score: float | None = Field(
        default=None,
        description="How undervalued the player is. Higher = more undervalued. >5 = strong buy, 3-5 = good target, <0 = overvalued",
    )
    undervalued_reasons: list[str] = Field(
        default_factory=list, description="Reasons explaining the undervalued score"
    )

    @field_validator("toi_per_game")
    @classmethod
    def toi_must_be_realistic(cls, v: float) -> float:
        """TOI should be realistic (players typically get 10-25 min/game)."""
        if v < 5 or v > 30:
            raise ValueError(
                f"TOI of {v} is unrealistic. Did you actually call get_comprehensive_player_stats?"
            )
        return v

    @field_validator("fenwick_pct", "corsi_pct")
    @classmethod
    def pct_must_be_realistic(cls, v: float) -> float:
        """Fenwick/Corsi % should be realistic (typically 40-60%)."""
        if v < 30 or v > 70:
            raise ValueError(
                f"Percentage of {v} is unrealistic. Did you actually call get_comprehensive_player_stats?"
            )
        return v


class TradeTarget(BaseModel):
    """A trade target with pitch.

    Pitches MUST include specific stats from MoneyPuck - generic pitches will be rejected.
    Each target MUST have detailed stats for BOTH the subject player AND the target player.
    """

    player_name: str = Field(description="Name of the trade target player")
    owner_team_name: str = Field(
        default="Unknown Team",
        description="Fantasy team that owns this player",
    )

    @field_validator("owner_team_name", mode="before")
    @classmethod
    def coerce_owner_team_name(cls, v: str | None) -> str:
        """Coerce None to default value."""
        if v is None:
            return "Unknown Team"
        return v

    target_stats_summary: str = Field(
        description="Summary of the TARGET player's stats: goals, assists, points, xGoals, Fenwick%, games, PPG",
        min_length=50,
    )
    pitch: str = Field(
        description="Convincing pitch that MUST include specific stats for BOTH players (xGoals, Fenwick%, TOI, goals, points, etc.)",
        min_length=150,
    )
    reasoning: str = Field(
        description="Detailed analysis comparing BOTH players' stats: points, xGoals, Fenwick%, schedule, line info",
        min_length=100,
    )

    @field_validator("pitch")
    @classmethod
    def pitch_must_contain_stats(cls, v: str) -> str:
        """Pitch must include specific advanced stats, not just ranks."""
        stat_keywords = [
            "xgoal",
            "x-goal",
            "expected goal",
            "fenwick",
            "corsi",
            "toi",
            "time on ice",
            "points per game",
            "ppg",
            "goals above",
            "points",
            "goals",
            "assists",
        ]
        v_lower = v.lower()
        if not any(kw in v_lower for kw in stat_keywords):
            raise ValueError(
                "Pitch must include specific stats (points, goals, xGoals, Fenwick%, etc.). "
                "Generic pitches based only on rank are not acceptable."
            )
        return v

    @field_validator("reasoning")
    @classmethod
    def reasoning_must_be_analytical(cls, v: str) -> str:
        """Reasoning must include actual analysis with specific stat comparisons."""
        weak_phrases = [
            "similar rank",
            "ranked around",
            "close in rank",
            "comparable rank",
        ]
        v_lower = v.lower()
        # If reasoning ONLY mentions rank without stats, reject it
        has_stats = any(
            kw in v_lower
            for kw in [
                "xgoal",
                "fenwick",
                "corsi",
                "toi",
                "schedule",
                "line",
                "games",
                "points",
                "goals",
                "assists",
                "ppg",
            ]
        )
        mentions_only_rank = any(phrase in v_lower for phrase in weak_phrases) and not has_stats
        if mentions_only_rank:
            raise ValueError(
                "Reasoning cannot be based only on rank. Must include advanced stats analysis."
            )
        return v


class TradeResponse(BaseModel):
    """Structured response for trade analysis.

    This response will be REJECTED if:
    - player_stats is missing entries for the subject player or any trade target
    - player_stats contains fabricated data (not from get_comprehensive_player_stats)
    - trade_targets have generic pitches without specific stats
    - schedule and linemate data are ignored when making trade recommendations
    """

    trade_direction: str = Field(
        description=(
            "Either 'trading_away' (user owns the subject player) "
            "or 'trading_for' (user wants to acquire)"
        )
    )
    subject_player: str = Field(description="The player the user asked about")
    player_stats: list[PlayerStats] = Field(
        description="Stats for all relevant players (subject player and trade targets). "
        "MUST include stats for EVERY player mentioned.",
        min_length=2,
    )
    trade_targets: list[TradeTarget] = Field(
        description="List of trade targets with pitches. Must have at least 1 target.",
        min_length=1,
    )
    summary: str = Field(
        description="Overall summary that references the advanced stats comparison",
        min_length=100,
    )

    @model_validator(mode="after")
    def validate_completeness(self) -> "TradeResponse":
        """Ensure we have stats for the subject player and all trade targets."""
        player_names_with_stats = {ps.name.lower() for ps in self.player_stats}
        target_names = {tt.player_name.lower() for tt in self.trade_targets}

        # For "trading_away", require subject player stats (the player being traded)
        # For "trading_for", subject player stats are optional (user may just want to acquire)
        if (
            self.trade_direction == "trading_away"
            and self.subject_player.lower() not in player_names_with_stats
        ):
            raise ValueError(
                f"Missing stats for subject player '{self.subject_player}'. "
                "You MUST call get_comprehensive_player_stats for the subject player."
            )

        # Check all trade targets have stats
        missing = target_names - player_names_with_stats
        if missing:
            raise ValueError(
                f"Missing stats for trade targets: {missing}. "
                "You MUST call get_comprehensive_player_stats for ALL trade targets before responding."
            )

        return self

    @field_validator("summary")
    @classmethod
    def summary_must_reference_stats(cls, v: str) -> str:
        """Summary must reference actual stats, not just ranks."""
        stat_keywords = [
            "xgoal",
            "expected",
            "fenwick",
            "corsi",
            "toi",
            "time on ice",
            "schedule",
            "games",
            "line",
        ]
        v_lower = v.lower()
        if not any(kw in v_lower for kw in stat_keywords):
            raise ValueError(
                "Summary must reference advanced stats (xGoals, Fenwick%, schedule, etc.). "
                "A summary based only on rank is not acceptable."
            )
        return v


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

3. Get comprehensive stats for ALL players (subject + targets) using get_comprehensive_player_stats:
   - Pass ALL player names in a single call (subject player + trade targets)
   - This returns NHL API IDs, MoneyPuck stats (goals, assists, xGoals, Fenwick%, etc.), and Yahoo rank
   - Also includes ownership info, injury status, schedule (games this week/next week), linemates
   - IMPORTANT: Each player now has an undervalued_score and undervalued_reasons

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
        get_comprehensive_player_stats,
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
