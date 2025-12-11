import duckdb


def get_nhl_stats_db_connection():
    return duckdb.connect(database='data/nhl_stats.db')


def get_platform_db_connection():
    return duckdb.connect(database='data/platform.db')
