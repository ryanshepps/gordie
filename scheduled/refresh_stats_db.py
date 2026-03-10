"""Refresh the DuckDB stats database from MoneyPuck CSV data."""

import tempfile
import time
from pathlib import Path

import duckdb

from module.logger import get_logger
from module.metrics import stats_db_last_refresh_timestamp, stats_db_refresh_total
from tools.stats.duckdb_connection import reset_stats_connection
from tools.stats.duckdb_schema import DB_PATH, MONEYPUCK_BASE_URL, SEASONS

logger = get_logger(__name__)

TABLE_TYPES = ["skaters", "goalies", "teams"]


def _csv_url(table_type: str, season: int) -> str:
    suffix = "lines" if table_type == "teams" else table_type
    return f"{MONEYPUCK_BASE_URL}/{season}/regular/{suffix}.csv"


def _load_table(conn: duckdb.DuckDBPyConnection, table_type: str) -> None:
    urls = [_csv_url(table_type, season) for season in SEASONS]
    union_query = " UNION ALL BY NAME ".join(
        f"SELECT *, {season} as season FROM read_csv_auto('{url}')"
        for season, url in zip(SEASONS, urls, strict=True)
    )
    conn.execute(f"CREATE OR REPLACE TABLE {table_type} AS ({union_query})")
    count = conn.execute(f"SELECT COUNT(*) FROM {table_type}").fetchone()
    logger.info(f"Loaded {table_type}: {count[0] if count else 0} rows")


def refresh_stats_db() -> None:
    tmp_dir = DB_PATH.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(suffix=".duckdb", dir=tmp_dir)
    tmp_path = Path(tmp_path_str)

    try:
        import os

        os.close(fd)
        tmp_path.unlink()

        conn = duckdb.connect(str(tmp_path))
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")
            for table_type in TABLE_TYPES:
                _load_table(conn, table_type)
        finally:
            conn.close()

        tmp_path.replace(DB_PATH)
        logger.info(f"Stats database refreshed at {DB_PATH}")

        reset_stats_connection()

        stats_db_refresh_total.labels(status="success").inc()
        stats_db_last_refresh_timestamp.set(time.time())

    except Exception:
        logger.exception("Failed to refresh stats database")
        stats_db_refresh_total.labels(status="error").inc()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
