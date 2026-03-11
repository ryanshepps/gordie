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
        "('Connor McDavid', 'EDM', 35, '5on5'), "
        "('Auston Matthews', 'TOR', 45, 'all'), "
        "('Leon Draisaitl', 'EDM', 42, 'all')"
    )
    conn.execute(
        "CREATE TABLE goalies (name VARCHAR, team VARCHAR, wins INTEGER, situation VARCHAR)"
    )
    conn.execute(
        "CREATE TABLE teams (team VARCHAR, wins INTEGER, situation VARCHAR)"
    )
    with patch("tools.stats.query_stats_db.get_stats_connection", return_value=conn):
        yield conn
    conn.close()


class TestQueryStatsDb:
    def test_returns_only_matching_situation(self, mock_connection):
        result = query_stats_db.invoke(
            {"sql": "SELECT name, goals FROM skaters ORDER BY goals DESC", "situation": "all"}
        )
        parsed = json.loads(result)

        names = [r["name"] for r in parsed["results"]]
        assert "Connor McDavid" in names
        assert len(parsed["results"]) == 3

    def test_5on5_situation_filters_correctly(self, mock_connection):
        result = query_stats_db.invoke(
            {"sql": "SELECT name, goals FROM skaters", "situation": "5on5"}
        )
        parsed = json.loads(result)

        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["name"] == "Connor McDavid"
        assert parsed["results"][0]["goals"] == 35

    def test_column_not_found_returns_available_columns(self, mock_connection):
        result = query_stats_db.invoke(
            {"sql": "SELECT nonexistent FROM skaters", "situation": "all"}
        )
        parsed = json.loads(result)

        assert "error" in parsed
        assert "available_columns" in parsed
        assert "name" in parsed["available_columns"]
        assert "goals" in parsed["available_columns"]

    def test_truncation_at_max_rows(self, mock_connection):
        values = ", ".join(f"('Player{i}', 'TST', {i}, 'all')" for i in range(MAX_ROWS + 10))
        mock_connection.execute(f"INSERT INTO skaters VALUES {values}")

        result = query_stats_db.invoke(
            {"sql": "SELECT * FROM skaters", "situation": "all"}
        )
        parsed = json.loads(result)

        assert len(parsed["results"]) == MAX_ROWS
        assert "truncated" in parsed["notice"].lower()

    def test_db_not_found_raises(self):
        with (
            patch(
                "tools.stats.query_stats_db.get_stats_connection",
                side_effect=FileNotFoundError("Stats database not found"),
            ),
            pytest.raises(FileNotFoundError),
        ):
            query_stats_db.invoke({"sql": "SELECT 1", "situation": "all"})
