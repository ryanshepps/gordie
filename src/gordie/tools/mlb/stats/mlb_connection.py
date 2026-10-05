from duckdb import DuckDBPyConnection

from gordie.runtime import current_runtime


def get_mlb_stats_connection() -> DuckDBPyConnection:
    return current_runtime().plugins.storage.stats_connection("mlb_stats.duckdb")


def reset_mlb_stats_connection() -> None:
    current_runtime().plugins.storage.reset_stats("mlb_stats.duckdb")
