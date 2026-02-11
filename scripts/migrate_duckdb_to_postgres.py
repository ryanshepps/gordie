"""One-time migration script: DuckDB → PostgreSQL.

Reads from the old DuckDB files (data/platform.db, data/nhl_stats.db)
and inserts all rows into the PostgreSQL database.

Prerequisites:
  - PostgreSQL running (docker compose up -d)
  - Alembic migrations applied (uv run alembic upgrade head)
  - Old DuckDB files still present in data/

Usage:
  uv run python scripts/migrate_duckdb_to_postgres.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb  # pyright: ignore[reportMissingImports]
from dotenv import load_dotenv
from sqlalchemy import text

from data.database import get_session

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORM_DB = os.path.join(PROJECT_ROOT, "data", "platform.db")
NHL_STATS_DB = os.path.join(PROJECT_ROOT, "data", "nhl_stats.db")

# Tables in FK-safe insertion order
PLATFORM_TABLES = [
    "users",
    "yahoo_leagues",
    "yahoo_user_teams",
    "yahoo_tokens",
    "email_threads",
    "notification_types",
    "notification_preferences",
    "conversation_summaries",
    "oauth_nonces",
]
NHL_TABLES = [
    "nhl_player_game_stats",
]


def migrate_table(duck_conn, pg_session, table_name: str) -> int:
    """Migrate a single table from DuckDB to PostgreSQL.

    Returns the number of rows migrated.
    """
    try:
        rows = duck_conn.execute(f"SELECT * FROM {table_name}").fetchall()
    except duckdb.CatalogException:  # pyright: ignore[reportAttributeAccessIssue]
        print(f"  SKIP {table_name} — table does not exist in DuckDB")
        return 0

    if not rows:
        print(f"  SKIP {table_name} — empty")
        return 0

    # Get column names
    columns = [desc[0] for desc in duck_conn.description]
    col_list = ", ".join(columns)
    param_list = ", ".join(f":{col}" for col in columns)

    insert_sql = text(
        f"INSERT INTO {table_name} ({col_list}) VALUES ({param_list}) "
        f"ON CONFLICT DO NOTHING"
    )

    for row in rows:
        params = dict(zip(columns, row, strict=False))
        pg_session.execute(insert_sql, params)

    pg_session.commit()
    print(f"  OK   {table_name} — {len(rows)} rows")
    return len(rows)


def main():
    total = 0
    session = get_session()

    try:
        # Migrate platform.db tables
        if os.path.exists(PLATFORM_DB):
            print(f"\nMigrating from {PLATFORM_DB}...")
            duck = duckdb.connect(PLATFORM_DB, read_only=True)
            for table in PLATFORM_TABLES:
                total += migrate_table(duck, session, table)
            duck.close()
        else:
            print(f"WARN: {PLATFORM_DB} not found, skipping platform tables")

        # Migrate nhl_stats.db tables
        if os.path.exists(NHL_STATS_DB):
            print(f"\nMigrating from {NHL_STATS_DB}...")
            duck = duckdb.connect(NHL_STATS_DB, read_only=True)
            for table in NHL_TABLES:
                total += migrate_table(duck, session, table)
            duck.close()
        else:
            print(f"WARN: {NHL_STATS_DB} not found, skipping NHL stats")

        print(f"\nDone. Migrated {total} total rows.")

        # Validate counts
        print("\nValidation — row counts in PostgreSQL:")
        for table in [*PLATFORM_TABLES, *NHL_TABLES]:
            result = session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            print(f"  {table}: {result}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
