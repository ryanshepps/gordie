import threading

import duckdb

from tools.mlb.stats.mlb_schema import MLB_DB_PATH

_connection: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def get_mlb_stats_connection() -> duckdb.DuckDBPyConnection:
    global _connection
    with _lock:
        if _connection is not None:
            return _connection.cursor()

        if not MLB_DB_PATH.exists():
            raise FileNotFoundError(
                f"MLB stats database not found at {MLB_DB_PATH}. "
                "Run the refresh_mlb_stats_db job to populate it."
            )

        _connection = duckdb.connect(str(MLB_DB_PATH), read_only=True)
        return _connection.cursor()


def reset_mlb_stats_connection() -> None:
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
        _connection = None
