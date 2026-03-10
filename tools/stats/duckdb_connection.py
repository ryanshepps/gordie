"""DuckDB connection management for the stats engine."""

import duckdb

from tools.stats.duckdb_schema import DB_PATH

_connection: duckdb.DuckDBPyConnection | None = None


def get_stats_connection() -> duckdb.DuckDBPyConnection:
    global _connection
    if _connection is not None:
        return _connection

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Stats database not found at {DB_PATH}. "
            "Run the refresh_stats_db job to populate it."
        )

    _connection = duckdb.connect(str(DB_PATH), read_only=True)
    return _connection


def reset_stats_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None
