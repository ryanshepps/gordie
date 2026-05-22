"""Refresh the DuckDB stats database from MoneyPuck CSV data."""

import os
import tempfile
import time
from pathlib import Path

import duckdb
import requests

from module.logger import get_logger
from module.metrics import stats_db_last_refresh_timestamp, stats_db_refresh_total
from tools.hockey.stats.duckdb_connection import reset_stats_connection
from tools.hockey.stats.duckdb_schema import DB_PATH, MONEYPUCK_BASE_URL, SEASONS

logger = get_logger(__name__)

TABLE_TYPES = ["skaters", "goalies", "teams"]
REQUEST_HEADERS = {"User-Agent": "fantasy-agent/1.0"}


def _csv_url(table_type: str, season: int) -> str:
    suffix = "lines" if table_type == "teams" else table_type
    return f"{MONEYPUCK_BASE_URL}/{season}/regular/{suffix}.csv"


def _download_csv(url: str, dest: Path) -> None:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    dest.write_bytes(response.content)


def _load_table(conn: duckdb.DuckDBPyConnection, table_type: str, csv_dir: Path) -> None:
    csv_files = sorted(csv_dir.glob(f"{table_type}_*.csv"))
    union_query = " UNION ALL BY NAME ".join(
        f"SELECT * FROM read_csv_auto('{csv_file}')" for csv_file in csv_files
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
        os.close(fd)
        tmp_path.unlink()

        with tempfile.TemporaryDirectory() as csv_dir_str:
            csv_dir = Path(csv_dir_str)

            for table_type in TABLE_TYPES:
                for season in SEASONS:
                    url = _csv_url(table_type, season)
                    dest = csv_dir / f"{table_type}_{season}.csv"
                    logger.info(f"Downloading {url}")
                    try:
                        _download_csv(url, dest)
                    except requests.HTTPError as exc:
                        if exc.response is not None and exc.response.status_code == 404:
                            logger.warning(
                                f"MoneyPuck has no {table_type} data for {season} (404), skipping"
                            )
                        else:
                            raise

            conn = duckdb.connect(str(tmp_path))
            try:
                for table_type in TABLE_TYPES:
                    _load_table(conn, table_type, csv_dir)
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
