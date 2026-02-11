"""Pydantic models for application data structures (not database schemas)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MatchupOpponent(BaseModel):
    """Opponent information in a fantasy matchup."""

    name: str
    team_key: str
    wins: int = 0
    losses: int = 0
    ties: int = 0

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}-{self.ties}"


class Matchup(BaseModel):
    """A single fantasy matchup."""

    week: int
    week_start: str = ""
    week_end: str = ""
    status: str = ""
    opponent: MatchupOpponent | None = None


class MatchupResponse(BaseModel):
    """Response from get_team_matchups."""

    matchups: list[Matchup] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class CurrentMatchup(BaseModel):
    """Current week's matchup summary."""

    opponent_name: str
    opponent_record: str
    week: int
    week_start: str
    week_end: str


class EnrichedFreeAgent(BaseModel):
    """Free agent with basic info and advanced stats."""

    name: str
    position: str | None = None
    team: str | None = None
    percent_owned: str | None = None
    goals: int = 0
    assists: int = 0
    corsi_pct: float | None = None
    games_this_week: int | None = None


class PlayerPerformance(BaseModel):
    """Player performance data for digest."""

    name: str
    position: str
    nhl_team: str
    points: float
    injury: str | None = None


class RosterPerformance(BaseModel):
    """Categorized roster performance."""

    top_performers: list[PlayerPerformance] = Field(default_factory=list)
    underperformers: list[PlayerPerformance] = Field(default_factory=list)
    injured: list[PlayerPerformance] = Field(default_factory=list)


class ScheduleTip(BaseModel):
    """A schedule-based recommendation."""

    team: str
    games_this_week: int
    player_names: list[str]
    tip_type: str  # "advantage" or "warning"


class DigestData(BaseModel):
    """All data needed to build the weekly digest."""

    league_name: str
    team_name: str
    current_week: int
    roster_performance: RosterPerformance
    current_matchup: CurrentMatchup | None = None
    hot_free_agents: list[EnrichedFreeAgent] = Field(default_factory=list)
    schedule_tips: list[ScheduleTip] = Field(default_factory=list)
