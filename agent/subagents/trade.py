"""Trade sub-agent for finding players to trade for"""

import logging
from typing import Annotated, Any

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field, field_validator, model_validator

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_moneypuck_stats import get_moneypuck_stats
from tools.player_comparison.get_player_line_info import get_player_line_info
from tools.player_comparison.get_team_schedule import get_team_schedule
from tools.yahoo.find_similar_ranked_players import find_similar_ranked_players
from tools.yahoo.get_league_teams import get_league_teams
from tools.yahoo.get_player_season_rank import get_player_season_rank
from tools.yahoo.get_team_roster import get_team_roster

logger = logging.getLogger(__name__)


class PlayerStats(BaseModel):
    """Stats for a single player from MoneyPuck.

    These stats MUST come from get_moneypuck_stats - do not fabricate values.
    """

    name: str = Field(description="Player's full name")
    team: str = Field(description="Team abbreviation")
    position: str = Field(description="Player position (C, LW, RW, D)")
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

    @field_validator("toi_per_game")
    @classmethod
    def toi_must_be_realistic(cls, v: float) -> float:
        """TOI should be realistic (players typically get 10-25 min/game)."""
        if v < 5 or v > 30:
            raise ValueError(
                f"TOI of {v} is unrealistic. Did you actually call get_moneypuck_stats?"
            )
        return v

    @field_validator("fenwick_pct", "corsi_pct")
    @classmethod
    def pct_must_be_realistic(cls, v: float) -> float:
        """Fenwick/Corsi % should be realistic (typically 40-60%)."""
        if v < 30 or v > 70:
            raise ValueError(
                f"Percentage of {v} is unrealistic. Did you actually call get_moneypuck_stats?"
            )
        return v


class TradeTarget(BaseModel):
    """A trade target with pitch.

    Pitches MUST include specific stats from MoneyPuck - generic pitches will be rejected.
    """

    player_name: str = Field(description="Name of the trade target player")
    owner_team_name: str = Field(description="Fantasy team that owns this player")
    pitch: str = Field(
        description="Convincing pitch that MUST include specific stats (xGoals, Fenwick%, TOI, etc.)",
        min_length=100,
    )
    reasoning: str = Field(
        description="Analysis that MUST reference advanced stats comparing both players",
        min_length=50,
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
        ]
        v_lower = v.lower()
        if not any(kw in v_lower for kw in stat_keywords):
            raise ValueError(
                "Pitch must include specific advanced stats (xGoals, Fenwick%, Corsi%, TOI, etc.). "
                "Generic pitches based only on rank are not acceptable."
            )
        return v

    @field_validator("reasoning")
    @classmethod
    def reasoning_must_be_analytical(cls, v: str) -> str:
        """Reasoning must include actual analysis, not just 'similar rank'."""
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
            for kw in ["xgoal", "fenwick", "corsi", "toi", "schedule", "line", "games"]
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
    - player_stats contains fabricated data (not from get_moneypuck_stats)
    - trade_targets have generic pitches without specific stats
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

        # Check subject player has stats
        if self.subject_player.lower() not in player_names_with_stats:
            raise ValueError(
                f"Missing MoneyPuck stats for subject player '{self.subject_player}'. "
                "You MUST call get_moneypuck_stats for the subject player."
            )

        # Check all trade targets have stats
        missing = target_names - player_names_with_stats
        if missing:
            raise ValueError(
                f"Missing MoneyPuck stats for trade targets: {missing}. "
                "You MUST call get_moneypuck_stats for ALL trade targets before responding."
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
Task: Find trade targets and provide detailed comparison analysis with convincing trade pitches.

You MUST complete ALL steps below. Do not skip any step.

## Step 1: Determine trade direction (CRITICAL - DO THIS FIRST)
- Use get_team_roster to fetch the user's current roster
- Check if the player mentioned in the request is ON the user's team
- This determines the TRADE DIRECTION:
  - If the player IS on their team → They want to TRADE AWAY this player (sell to opponents)
  - If the player is NOT on their team → They want to TRADE FOR this player (acquire from opponents)

## Step 2: Get the subject player's info
- Use get_player_season_rank to find the player's current fantasy rank
- Use fuzzy_resolve_nhl_api_player_ids to get the NHL API player ID
- Use get_moneypuck_stats to get their advanced stats (TOI, xGoals, Fenwick, Corsi, etc.)

## Step 3: Find trade targets
- Use find_similar_ranked_players to find players with similar or better ranks
- Select 3-5 promising targets from the results

## Step 4: Get detailed stats for EACH trade target (CRITICAL - DO NOT SKIP)
- Use fuzzy_resolve_nhl_api_player_ids with ALL target player names to get their NHL API IDs
  IMPORTANT: You MUST use fuzzy_resolve_nhl_api_player_ids to get NHL API player IDs.
  The player IDs from find_similar_ranked_players are Yahoo IDs, NOT NHL API IDs.
  get_moneypuck_stats requires NHL API player IDs (8-digit numbers like 8478402).
- Use get_moneypuck_stats with those NHL API IDs to get their advanced statistics
- Compare stats: TOI, xGoals, goals above expected, Fenwick%, points per game

## Step 5: Check schedules (CRITICAL - DO NOT SKIP)
- Extract the team abbreviations for the subject player AND all trade targets
- Use get_team_schedule with all team abbreviations to compare upcoming games
- More games = more fantasy point opportunities

## Step 6: Check line information (CRITICAL - DO NOT SKIP)
- Use get_player_line_info with the NHL API player IDs (from step 4)
- Identify which line each player is on (1st line = better)
- Identify elite linemates (playing with stars = better production)

## Step 7: Build trade pitches (DIRECTION MATTERS!)

CRITICAL: Your final output MUST include the actual stats you gathered in steps 2-6.
Do NOT just give generic pitches - include the specific numbers (goals, assists, points,
xGoals, Fenwick%, TOI, schedule info, line info) for both the subject player and each target.

**If TRADING AWAY (user owns the subject player):**
The user wants to CONVINCE OPPONENTS to take their player. Pitches must SELL their player.

DO NOT pitch why the trade targets are good - the user already knows that!
Instead, provide pitches the user can SEND TO OPPONENTS to convince them to give up
their player in exchange for the user's player.

For EACH trade target:
- Show the relevant stats for both players so the user can see the comparison
- Provide a pitch that sells the USER'S PLAYER using specific numbers:
  - Strong underlying stats (xGoals, Fenwick%) even if points are down
  - Historical production and name recognition
  - Upcoming schedule advantages
  - Elite linemates they usually play with

**If TRADING FOR (user wants to acquire a player they don't own):**
The user needs reasons why opponents might be willing to sell their player:
- Show the relevant stats for the target player
- Highlight why the target player might be undervalued by their current owner
- Find reasons the current owner might be motivated to sell
- Suggest what the user could offer in return

IMPORTANT: Include the actual stats you gathered. Generic advice without numbers is unacceptable.

## Step 8: Populate the structured response

You MUST return a structured response with the following fields:
- trade_direction: "trading_away" if user owns the player, "trading_for" if they want it
- subject_player: The name of the player the user asked about
- player_stats: A list of PlayerStats for ALL relevant players (subject + trade targets)
  - Include: name, team, position, games_played, goals, assists, points, toi_per_game,
    x_goals, goals_above_expected, fenwick_pct, corsi_pct, points_per_game
  - Get these values from the MoneyPuck stats you fetched
- trade_targets: A list of TradeTarget objects with:
  - player_name: The trade target's name
  - owner_team_name: The fantasy team that currently owns this player
  - pitch: A convincing pitch to send to the owner
  - reasoning: Your analysis of why this is a good trade target
- summary: An overall summary and recommendation

User email: {user_email}
League ID: {league_id}
Team ID: {team_id}
"""

agent = create_subagent(
    name="trade",
    system_prompt=_player_assessment_task,
    tools=[
        get_team_roster,
        get_league_teams,
        get_moneypuck_stats,
        fuzzy_resolve_nhl_api_player_ids,
        get_team_schedule,
        get_player_line_info,
        get_player_season_rank,
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
    """Find players to trade for based on the user's request.

    Args:
        request (str): The user's request for players to trade for.
        user_email (str): The email address of the user.
        league_id (str): The ID of the fantasy league.
        team_id (str): The ID of the team.
        state: The state of the agent. Defaults to None.

    Returns:
        str: The response from the agent.
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

    response = extract_response(
        result, fallback_message="I ran into an error while processing your trade request."
    )

    logger.info(f"Trade sub-agent response: {response}")
    return response
