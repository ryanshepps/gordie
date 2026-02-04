from __future__ import annotations

import logging

import duckdb
from pydantic import BaseModel, Field

from client.duck_db_client import get_nhl_stats_db_connection, get_platform_db_connection
from module.logger import get_logger

logger = get_logger(__name__, level=logging.DEBUG)


# =============================================================================
# Pydantic Models for Weekly Digest
# =============================================================================


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
    # Advanced stats (from comprehensive stats tool)
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


# =============================================================================
# Database Schema Functions
# =============================================================================


def create_nhl_player_game_stats_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for NHL player statistics with daily game tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nhl_player_game_stats (
            nhl_api_player_id INTEGER NOT NULL,
            nhl_api_game_id INTEGER NOT NULL,
            game_date DATE NOT NULL,
            full_name VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            goals INTEGER,
            assists INTEGER,
            points INTEGER,
            plus_minus INTEGER,
            pim INTEGER,
            hits INTEGER,
            power_play_goals INTEGER,
            sog INTEGER,
            faceoff_winning_pctg DECIMAL(5, 2),
            toi VARCHAR,
            blocked_shots INTEGER,
            shifts INTEGER,
            giveaways INTEGER,
            takeaways INTEGER,
            corsi_for INTEGER,
            fenwick_for INTEGER,
            missed_shots INTEGER,
            PRIMARY KEY (nhl_api_player_id, nhl_api_game_id)
        )
    """)
    logger.debug("Created nhl_player_game_stats table")


def create_users_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for user information."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.debug("Created users table")


def create_yahoo_league_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for Yahoo league information."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yahoo_leagues (
            league_id TEXT PRIMARY KEY,
            game_key TEXT NOT NULL,
            league_name TEXT NOT NULL,
            league_type TEXT NOT NULL,
            league_settings TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.debug("Created yahoo_leagues table")


def create_yahoo_user_teams_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for user information."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yahoo_user_teams (
            league_id TEXT NOT NULL,
            team_id TEXT NOT NULL,
            user_email TEXT NOT NULL,
            team_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (league_id, team_id, user_email),
            FOREIGN KEY (user_email) REFERENCES users(email),
            FOREIGN KEY (league_id) REFERENCES yahoo_leagues(league_id)
        )
    """)
    logger.debug("Created yahoo_user_teams table")


def create_yahoo_tokens_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for Yahoo token information."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yahoo_tokens (
            user_email TEXT PRIMARY KEY,
            yahoo_email TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            token_time TIMESTAMP NOT NULL,
            token_type TEXT NOT NULL DEFAULT 'Bearer',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    logger.debug("Created yahoo_tokens table")


def create_email_threads_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for tracking email thread Message-IDs.

    This table maps Mailgun Message-IDs to conversation thread_ids,
    enabling proper email threading when users reply to emails.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_threads (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            user_email TEXT NOT NULL,
            subject TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    # Create index for faster lookups by thread_id
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_threads_thread_id
        ON email_threads(thread_id)
    """)
    # Create index for lookups by user_email
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_threads_user_email
        ON email_threads(user_email)
    """)
    logger.debug("Created email_threads table")


def create_notification_types_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for registry of available notification types."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_types (
            type_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            default_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.debug("Created notification_types table")


def seed_notification_types(conn: duckdb.DuckDBPyConnection) -> None:
    """Seed default notification types."""
    conn.execute("""
        INSERT INTO notification_types (type_key, display_name, description, default_enabled)
        VALUES ('weekly_digest', 'Weekly Digest', 'Weekly fantasy hockey summary with roster updates and recommendations', TRUE)
        ON CONFLICT (type_key) DO NOTHING
    """)
    conn.commit()
    logger.debug("Seeded notification_types table")


def create_notification_preferences_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for user notification preferences per league."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_preferences (
            user_email TEXT NOT NULL,
            league_id TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            enabled BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_email, league_id, notification_type),
            FOREIGN KEY (user_email) REFERENCES users(email),
            FOREIGN KEY (league_id) REFERENCES yahoo_leagues(league_id),
            FOREIGN KEY (notification_type) REFERENCES notification_types(type_key)
        )
    """)
    logger.debug("Created notification_preferences table")


if __name__ == "__main__":
    nhl_stats_conn = get_nhl_stats_db_connection()
    create_nhl_player_game_stats_table(nhl_stats_conn)
    nhl_stats_conn.close()

    platform_conn = get_platform_db_connection()
    create_users_table(platform_conn)
    create_yahoo_league_table(platform_conn)
    create_yahoo_user_teams_table(platform_conn)
    create_yahoo_tokens_table(platform_conn)
    create_email_threads_table(platform_conn)
    create_notification_types_table(platform_conn)
    seed_notification_types(platform_conn)
    create_notification_preferences_table(platform_conn)
    platform_conn.close()

    logger.info("Database setup complete")
