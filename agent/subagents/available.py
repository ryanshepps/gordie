"""Available players sub-agent for finding streaming/pickup opportunities"""

import logging
from typing import Annotated, Any

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field, field_validator, model_validator

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from tools.yahoo.get_available_players_with_stats import get_available_players_with_stats
from tools.yahoo.get_team_roster import get_team_roster

logger = logging.getLogger(__name__)


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
    ownership_type: str | None = Field(
        default=None, description="Ownership type (waivers, freeagents, team)"
    )
    percent_owned: str | None = Field(default=None, description="Percent owned in leagues")

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


class AvailablePickup(BaseModel):
    """A single pickup recommendation from available players pool.

    Pitches MUST include specific stats - generic pitches will be rejected.
    Each pickup MUST have detailed stats comparing to drop candidate.
    """

    player_name: str = Field(description="Name of the available player to pick up")
    availability_type: str = Field(
        description="Availability type: 'FA' (free agent, immediate add) or 'W' (waivers, requires claim)"
    )
    stats_summary: str = Field(
        description="Summary of key stats: goals, assists, xGoals, Fenwick%, schedule",
        min_length=50,
    )
    pitch: str = Field(
        description="Why pick up this player - MUST include 5+ specific stats (xGoals, Fenwick%, TOI, schedule, GAE, points)",
        min_length=150,
    )
    reasoning: str = Field(
        description="Detailed comparison to drop candidate with specific stats (xGoals, Fenwick%, schedule, deployment)",
        min_length=100,
    )
    priority_level: str = Field(
        description="Priority level: 'must_add' (undervalued_score >5), 'strong_add' (3-5), 'consider' (0-3)"
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
            "schedule",
            "games",
            "points",
            "goals",
            "assists",
        ]
        v_lower = v.lower()
        if not any(kw in v_lower for kw in stat_keywords):
            raise ValueError(
                "Pitch must include specific stats (points, goals, xGoals, Fenwick%, schedule, etc.). "
                "Generic pitches based only on rank are not acceptable."
            )
        return v

    @field_validator("reasoning")
    @classmethod
    def reasoning_must_be_analytical(cls, v: str) -> str:
        """Reasoning must include actual analysis with specific stat comparisons."""
        stat_keywords = [
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
        v_lower = v.lower()
        has_stats = any(kw in v_lower for kw in stat_keywords)
        if not has_stats:
            raise ValueError(
                "Reasoning must include advanced stats analysis (xGoals, Fenwick%, schedule, etc.)."
            )
        return v


class DropCandidate(BaseModel):
    """A droppable/streamable player from user's roster."""

    player_name: str = Field(description="Name of the droppable player")
    stats_summary: str = Field(
        description="Summary of why this player is droppable - stats + context",
        min_length=50,
    )
    drop_rationale: str = Field(
        description="Specific reasons with stats comparison (undervalued_score, GAE, Fenwick%, schedule)",
        min_length=80,
    )


class AvailablePlayersResponse(BaseModel):
    """Structured response for available players analysis.

    This response will be REJECTED if:
    - player_stats is missing entries for drop candidates or pickup recommendations
    - player_stats contains fabricated data (not from get_comprehensive_player_stats)
    - pickups have generic pitches without specific stats
    - schedule and linemate data are ignored when making recommendations
    """

    drop_candidates: list[DropCandidate] = Field(
        default_factory=list,
        description="Suggested players to drop from roster (empty if user specified drop candidate)",
    )
    player_stats: list[PlayerStats] = Field(
        description="Stats for ALL players involved (drop candidates + FA picks + W picks). "
        "MUST include stats for EVERY player mentioned.",
        min_length=1,
    )
    free_agent_recommendations: list[AvailablePickup] = Field(
        default_factory=list,
        description="Free agent recommendations (immediate add) - top pick + 2-3 alternatives",
    )
    waiver_recommendations: list[AvailablePickup] = Field(
        default_factory=list,
        description="Waiver recommendations (requires claim) - top pick + 2-3 alternatives",
    )
    summary: str = Field(
        description="Overall summary that references FA/W timing and advanced stats comparison",
        min_length=100,
    )

    @model_validator(mode="after")
    def validate_completeness(self) -> "AvailablePlayersResponse":
        """Ensure we have stats for all drop candidates and pickup recommendations."""
        player_names_with_stats = {ps.name.lower() for ps in self.player_stats}

        # Check drop candidates have stats
        for dc in self.drop_candidates:
            if dc.player_name.lower() not in player_names_with_stats:
                raise ValueError(
                    f"Missing stats for drop candidate '{dc.player_name}'. "
                    "You MUST call get_comprehensive_player_stats for all drop candidates."
                )

        # Check all FA picks have stats
        for fa in self.free_agent_recommendations:
            if fa.player_name.lower() not in player_names_with_stats:
                raise ValueError(
                    f"Missing stats for FA pickup '{fa.player_name}'. "
                    "You MUST call get_comprehensive_player_stats for ALL pickup recommendations."
                )

        # Check all W picks have stats
        for w in self.waiver_recommendations:
            if w.player_name.lower() not in player_names_with_stats:
                raise ValueError(
                    f"Missing stats for waiver pickup '{w.player_name}'. "
                    "You MUST call get_comprehensive_player_stats for ALL pickup recommendations."
                )

        return self

    @field_validator("summary")
    @classmethod
    def summary_must_reference_stats_and_timing(cls, v: str) -> str:
        """Summary must reference both advanced stats AND FA/W timing."""
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
        timing_keywords = [
            "free agent",
            "waiver",
            "fa",
            "immediately",
            "claim",
            "streaming",
        ]

        v_lower = v.lower()
        has_stats = any(kw in v_lower for kw in stat_keywords)
        has_timing = any(kw in v_lower for kw in timing_keywords)

        if not has_stats or not has_timing:
            raise ValueError(
                "Summary must reference both advanced stats (xGoals, Fenwick%, schedule, etc.) "
                "AND FA/W timing information (immediate add vs claim required)."
            )
        return v


_available_players_task = """
Find available player pickups (free agents + waivers) with detailed statistical analysis for streaming/add-drop strategy.

## CRITICAL: FA vs W Separation

Always provide SEPARATE recommendations for:
- Free Agents (FA): Can be added IMMEDIATELY without waiver claim
- Waivers (W): Require waiver claim, processed on waiver day

For each category, provide:
- Top recommendation (highest composite score)
- 2-3 alternatives for depth/options

## Simplified Workflow (1-2 tool calls only)

1. **Call get_available_players_with_stats ONCE:**
   - This fetches BOTH FA and W players with comprehensive stats already included
   - Returns free_agents and waiver_players lists with comprehensive_stats embedded
   - Stats include: undervalued_score, schedule, linemates, MoneyPuck analytics

2. **If user didn't specify who to drop, call get_team_roster:**
   - Get user's roster to identify drop candidates
   - Look for players with low undervalued_score (overvalued/droppable)

3. **Analyze the returned data:**
   - Players are pre-sorted by recent performance (AR/lastweek)
   - comprehensive_stats contains all MoneyPuck data, schedule, linemates
   - Use undervalued_score to prioritize:
     - Score > 5: MUST ADD
     - Score 3-5: STRONG ADD
     - Score 0-3: CONSIDER
     - Score < 0: OVERVALUED (droppable)

4. **Build recommendations from the data:**
   - Select top FA players with best undervalued_score + schedule
   - Select top W players with best undervalued_score + schedule
   - Build pitches using the comprehensive_stats data

## Priority Scoring

Use undervalued_score from comprehensive_stats plus:
- Schedule: +2 if 7+ games next 2 weeks, +1 if 5-6 games
- Regression potential: +2 if GAE < -3 (shooting unlucky)
- Deployment: +2 if line 1, +1 if line 2
- Possession: +2 if Fenwick > 54%

## Pitch Requirements

Each pitch MUST include 5+ specific stat values from comprehensive_stats:
- Expected goals (xGoals)
- Fenwick% or Corsi%
- Time on ice
- Schedule (games_remaining_this_week, games_next_week)
- Goals Above Expected (regression direction)

## Response Requirements

Return AvailablePlayersResponse with:
- drop_candidates (if identified from roster)
- player_stats for ALL players mentioned
- free_agent_recommendations (top + 2-3 alternatives)
- waiver_recommendations (top + 2-3 alternatives)
- summary referencing FA/W timing AND key advanced stats

User: {user_email} | League: {league_id} | Team: {team_id}
"""

agent = create_subagent(
    name="available",
    system_prompt=_available_players_task,
    tools=[
        get_team_roster,
        get_available_players_with_stats,
    ],
    response_format=AvailablePlayersResponse,
)


@tool
def available_players(
    request: str,
    user_email: str,
    league_id: str,
    team_id: str,
    state: Annotated[dict[str, Any], InjectedState] | None = None,
):
    """Analyze available players and recommend pickups for streaming/add-drop strategy.

    Use this tool for:
    - Finding available player pickups (FA + waivers) based on advanced stats
    - Comparing potential drops to available players
    - Evaluating schedule-based streaming opportunities
    - Questions like "who should I pick up", "streaming options", "should I drop X"
    - Identifying droppable/streamable players on user's roster

    This tool performs comprehensive analysis including MoneyPuck advanced stats,
    schedule analysis, linemate information, and undervalued player scoring.
    Provides separate recommendations for free agents (immediate add) and waivers (claim required).

    Args:
        request (str): The user's request in natural language.
        user_email (str): The email address of the user.
        league_id (str): The ID of the fantasy league.
        team_id (str): The ID of the team.
        state: The state of the agent. Defaults to None.

    Returns:
        str: Detailed available players analysis with separate FA and waiver recommendations,
             including statistical comparisons and streaming strategy.
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

    # Check for structured response first
    structured = result.get("structured_response")
    if structured:
        logger.info(f"Available players sub-agent structured response: {structured}")
        return str(structured)

    response = extract_response(
        result,
        fallback_message="I ran into an error while processing your available players request.",
    )

    logger.info(f"Available players sub-agent response: {response}")
    return response
