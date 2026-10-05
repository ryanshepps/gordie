"""Data models for the news digest system.

This module defines the structured data types for alerts and digests
used throughout the news agent pipeline.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# =============================================================================
# Base and Raw Alert Models
# =============================================================================


class RosterPlayer(BaseModel):
    name: str
    team: str
    roster_slot: str
    position: str


class BaseAlert(BaseModel):
    """Base class for all alert types."""

    player_name: str


class InjuryAlert(BaseAlert):
    """Alert for player injuries from ESPN RSS."""

    team: str
    status: str  # "OUT", "DTD", "IR"
    description: str


class TradeAlert(BaseAlert):
    """Alert for player trades from RSS feeds."""

    from_team: str
    to_team: str
    trade_date: str


class MatchupAlert(BaseAlert):
    """Alert for favorable game-day matchups."""

    opponent: str
    opponent_weakness_metric: float
    metric_label: str


# =============================================================================
# User-Enriched Alert Models
# =============================================================================


class UserInjuryAlert(InjuryAlert):
    """Injury alert enriched with fantasy context."""

    fantasy_impact: str
    has_game_today: bool = False
    is_new_injury: bool = True
    already_on_ir_slot: bool = False
    next_game_info: str | None = None


class UserTradeAlert(TradeAlert):
    """Trade alert enriched with fantasy context."""

    fantasy_impact: str


class UserMatchupAlert(MatchupAlert):
    """Matchup alert enriched with fantasy context."""

    fantasy_impact: str


# =============================================================================
# News Digest Model
# =============================================================================


class NewsDigest(BaseModel):
    """Complete news digest for a single user/league combination."""

    user_email: str
    league_id: str
    team_id: str
    league_name: str
    team_name: str
    injury_alerts: list[UserInjuryAlert] = Field(default_factory=list)
    trade_alerts: list[UserTradeAlert] = Field(default_factory=list)
    matchup_alerts: list[UserMatchupAlert] = Field(default_factory=list)
    bench_reminders: list[str] = Field(default_factory=list)
    position_conflicts: dict[str, list[str]] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)

    def has_alerts(self) -> bool:
        """Check if this digest contains any alerts."""
        return bool(
            self.injury_alerts or self.trade_alerts or self.matchup_alerts or self.bench_reminders
        )

    @property
    def total_alerts(self) -> int:
        """Get total number of alerts in this digest."""
        return len(self.injury_alerts) + len(self.trade_alerts) + len(self.matchup_alerts)


# =============================================================================
# Raw News Collection Model
# =============================================================================


class RawNewsCollection(BaseModel):
    """Collection of raw alerts fetched from all sources.

    This is cached and shared across all users for a single job run.
    """

    injuries: list[InjuryAlert] = Field(default_factory=list)
    trades: list[TradeAlert] = Field(default_factory=list)
    matchups: list[MatchupAlert] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.now)
