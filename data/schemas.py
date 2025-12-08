import duckdb
import logging
from pathlib import Path
from module.logger import get_logger

logger = get_logger(__name__, level=logging.DEBUG)

def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Connect to the NHL stats DuckDB database."""
    # Get the data directory path (same as run_duckdb.sh)
    data_dir = Path(__file__).parent
    db_path = data_dir / "nhl_stats.db"

    logger.debug(f"Connecting to DuckDB at: {db_path}")
    conn = duckdb.connect(str(db_path))
    return conn


def create_player_stats_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create table for NHL player statistics with daily game tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            nhl_api_player_id INTEGER NOT NULL,
            nhl_api_game_id INTEGER NOT NULL,
            game_date DATE NOT NULL,
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
            PRIMARY KEY (nhl_api_player_id, nhl_api_game_id)
        )
    """)
    logger.debug("Created player_stats table")


if __name__ == "__main__":
    conn = get_db_connection()
    create_player_stats_table(conn)
    conn.close()
    logger.info("Database setup complete")
