from duckdb import DuckDBPyConnection

from gordie.runtime import current_runtime


def get_mlb_stats_connection() -> DuckDBPyConnection:
    return current_runtime().statistics.connection("mlb_stats.duckdb")


def reset_mlb_stats_connection() -> None:
    current_runtime().statistics.reset("mlb_stats.duckdb")
