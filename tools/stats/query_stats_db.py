"""Tool for querying the DuckDB stats database."""

import json
import re
from typing import Literal

import duckdb
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.stats.duckdb_connection import get_stats_connection
from tools.stats.duckdb_schema import TABLES, TOOL_DESCRIPTION
from tools.stats.mlb_connection import get_mlb_stats_connection
from tools.stats.mlb_schema import MLB_TABLES, MLB_TOOL_DESCRIPTION

logger = get_logger(__name__)

MAX_ROWS = 50

Sport = Literal["hockey", "baseball"]
Situation = Literal["all", "5on5", "5on4", "4on5"]

COMBINED_TOOL_DESCRIPTION = (
    "# Hockey Stats\n\n"
    + TOOL_DESCRIPTION
    + "\n\n---\n\n# Baseball Stats\n\n"
    + MLB_TOOL_DESCRIPTION
)


class QueryStatsDbInput(BaseModel):
    sql: str = Field(description="DuckDB SQL query to execute against the stats database")
    sport: Sport = Field(description="Which sport's stats database to query: 'hockey' or 'baseball'")
    situation: Situation = Field(
        default="all",
        description=(
            "Hockey only — ignored for baseball. "
            "'all' for totals, '5on5' for even-strength, "
            "'5on4' for power play, '4on5' for penalty kill."
        ),
    )


SITUATION_FILTERED_TABLES = ["skaters", "goalies"]
ALL_TABLES = [*SITUATION_FILTERED_TABLES, "teams"]


def _inject_situation(sql: str, situation: str) -> str:
    ctes = [
        f"_{t} AS (SELECT * FROM {t} WHERE situation = '{situation}')"
        for t in SITUATION_FILTERED_TABLES
    ]
    ctes.append("_teams AS (SELECT * FROM teams)")
    rewritten = sql
    for t in ALL_TABLES:
        rewritten = re.sub(rf"\b{t}\b", f"_{t}", rewritten)
    return f"WITH {', '.join(ctes)} {rewritten}"


@tool(args_schema=QueryStatsDbInput, description=COMBINED_TOOL_DESCRIPTION)
def query_stats_db(sql: str, sport: Sport, situation: Situation = "all") -> str:
    """Execute a SQL query against the stats DuckDB database."""
    tables = MLB_TABLES if sport == "baseball" else TABLES
    try:
        if sport == "baseball":
            conn = get_mlb_stats_connection()
            wrapped_sql = sql
        else:
            conn = get_stats_connection()
            wrapped_sql = _inject_situation(sql, situation)

        result = conn.execute(wrapped_sql)

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
        conn = get_mlb_stats_connection() if sport == "baseball" else get_stats_connection()
        referenced = [t for t in tables if t in sql.lower()]
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
