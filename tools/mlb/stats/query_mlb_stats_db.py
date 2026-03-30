import json

import duckdb
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.mlb.stats.mlb_connection import get_mlb_stats_connection
from tools.mlb.stats.mlb_schema import MLB_TABLES, MLB_TOOL_DESCRIPTION

logger = get_logger(__name__)

MAX_ROWS = 50


class QueryMlbStatsDbInput(BaseModel):
    sql: str = Field(description="DuckDB SQL query to execute against the MLB stats database")


@tool(args_schema=QueryMlbStatsDbInput, description=MLB_TOOL_DESCRIPTION)
def query_mlb_stats_db(sql: str) -> str:
    """Execute a SQL query against the MLB stats DuckDB database."""
    try:
        conn = get_mlb_stats_connection()
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

    except FileNotFoundError:
        raise
    except duckdb.BinderException as exc:
        conn = get_mlb_stats_connection()
        referenced = [t for t in MLB_TABLES if t in sql.lower()]
        schema_hints: list[str] = []
        for table in referenced:
            cols = [row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()]
            schema_hints.append(f"{table} columns: {', '.join(cols)}")
        hint = "\n".join(schema_hints)
        return json.dumps({
            "error": str(exc),
            "available_columns": hint,
        })
    except duckdb.Error:
        raise
