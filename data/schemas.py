import logging

import duckdb

from client.duck_db_client import get_nhl_stats_db_connection, get_platform_db_connection
from module.logger import get_logger

logger = get_logger(__name__, level=logging.DEBUG)


def create_nhl_player_stats_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for NHL player statistics with daily game tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nhl_player_stats (
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
    logger.debug("Created nhl_player_stats table")


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


if __name__ == "__main__":
    nhl_stats_conn = get_nhl_stats_db_connection()
    create_nhl_player_stats_table(nhl_stats_conn)
    nhl_stats_conn.close()

    platform_conn = get_platform_db_connection()
    create_users_table(platform_conn)
    create_yahoo_league_table(platform_conn)
    create_yahoo_user_teams_table(platform_conn)
    create_yahoo_tokens_table(platform_conn)
    platform_conn.close()

    logger.info("Database setup complete")
