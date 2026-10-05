from duckdb import DuckDBPyConnection

from gordie.runtime import current_runtime


def get_stats_connection() -> DuckDBPyConnection:
    return current_runtime().plugins.storage.stats_connection("moneypuck_stats.duckdb")


def reset_stats_connection() -> None:
    current_runtime().plugins.storage.reset_stats("moneypuck_stats.duckdb")
