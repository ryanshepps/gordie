"""Tests for the query_stats_db tool."""

import json
from unittest.mock import patch

import duckdb
import pytest

from tools.stats.query_stats_db import MAX_ROWS, query_stats_db


@pytest.fixture
def mock_connection():
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE skaters (name VARCHAR, team VARCHAR, goals INTEGER, situation VARCHAR)"
    )
    conn.execute(
        "INSERT INTO skaters VALUES "
        "('Connor McDavid', 'EDM', 50, 'all'), "
        "('Auston Matthews', 'TOR', 45, 'all'), "
        "('Leon Draisaitl', 'EDM', 42, 'all')"
    )
    with patch("tools.stats.query_stats_db.get_stats_connection", return_value=conn):
        yield conn
    conn.close()


class TestQueryStatsDb:
    def test_valid_sql_returns_json_results(self, mock_connection):
        result = query_stats_db.invoke(
            {"sql": "SELECT name, goals FROM skaters ORDER BY goals DESC LIMIT 2"}
        )
        parsed = json.loads(result)

        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["name"] == "Connor McDavid"
        assert parsed["results"][0]["goals"] == 50

    def test_invalid_sql_returns_error_string(self, mock_connection):
        result = query_stats_db.invoke({"sql": "SELECT nonexistent FROM skaters"})

        assert "error" in result.lower()

    def test_truncation_at_max_rows(self, mock_connection):
        values = ", ".join(f"('Player{i}', 'TST', {i}, 'all')" for i in range(MAX_ROWS + 10))
        mock_connection.execute(f"INSERT INTO skaters VALUES {values}")

        result = query_stats_db.invoke({"sql": "SELECT * FROM skaters"})
        parsed = json.loads(result)

        assert len(parsed["results"]) == MAX_ROWS
        assert "truncated" in parsed["notice"].lower()

    def test_db_not_found_returns_error(self):
        with patch(
            "tools.stats.query_stats_db.get_stats_connection",
            side_effect=FileNotFoundError("Stats database not found"),
        ):
            result = query_stats_db.invoke({"sql": "SELECT 1"})

        assert "not found" in result.lower()
