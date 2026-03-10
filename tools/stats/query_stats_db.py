"""Tool for querying the DuckDB stats database."""

import json

import duckdb
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.stats.duckdb_connection import get_stats_connection
from tools.stats.duckdb_schema import TOOL_DESCRIPTION

logger = get_logger(__name__)

MAX_ROWS = 50


class QueryStatsDbInput(BaseModel):
    sql: str = Field(description="DuckDB SQL query to execute against the stats database")


@tool(args_schema=QueryStatsDbInput, description=TOOL_DESCRIPTION)
def query_stats_db(sql: str) -> str:
    """Execute a SQL query against the MoneyPuck stats DuckDB database."""
    try:
        conn = get_stats_connection()
        result = conn.execute(sql)

        columns = [desc[0] for desc in result.description]
        rows = result.fetchmany(MAX_ROWS + 1)

        truncated = len(rows) > MAX_ROWS
        if truncated:
            rows = rows[:MAX_ROWS]

        records = [dict(zip(columns, row, strict=True)) for row in rows]

        output: dict[str, list[dict[str, str | int | float | None]] | str] = {
            "results": records
        }
        if truncated:
            output["notice"] = f"Results truncated to {MAX_ROWS} rows."

        return json.dumps(output, default=str)

    except FileNotFoundError as e:
        logger.error(f"Stats DB not found: {e}")
        return f"Error: {e}"
    except duckdb.Error as e:
        logger.warning(f"DuckDB query error: {e}")
        return f"SQL error: {e}"
