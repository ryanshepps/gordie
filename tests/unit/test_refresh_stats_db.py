"""Tests for the refresh_stats_db job."""

from unittest.mock import patch

import duckdb
import pytest

from scheduled.refresh_stats_db import refresh_stats_db


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    test_db_path = tmp_path / "moneypuck_stats.duckdb"
    monkeypatch.setattr("scheduled.refresh_stats_db.DB_PATH", test_db_path)
    monkeypatch.setattr("tools.stats.duckdb_connection.DB_PATH", test_db_path)
    return test_db_path


def _noop_load_table(conn: duckdb.DuckDBPyConnection, table_type: str) -> None:
    conn.execute(f"CREATE OR REPLACE TABLE {table_type} (name VARCHAR, season INTEGER)")
    conn.execute(f"INSERT INTO {table_type} VALUES ('Test Player', 2025)")


class TestRefreshStatsDb:
    def test_successful_refresh_creates_db_and_resets_connection(self, isolate_db):
        with (
            patch("scheduled.refresh_stats_db._load_table", side_effect=_noop_load_table),
            patch("scheduled.refresh_stats_db.reset_stats_connection") as mock_reset,
        ):
            refresh_stats_db()

        assert isolate_db.exists()
        mock_reset.assert_called_once()

        conn = duckdb.connect(str(isolate_db), read_only=True)
        result = conn.execute("SELECT name FROM skaters").fetchone()
        conn.close()
        assert result is not None
        assert result[0] == "Test Player"

    def test_failed_download_preserves_existing_db(self, isolate_db):
        isolate_db.write_text("existing")

        with (
            patch(
                "scheduled.refresh_stats_db._load_table",
                side_effect=Exception("download failed"),
            ),
            pytest.raises(Exception, match="download failed"),
        ):
            refresh_stats_db()

        assert isolate_db.read_text() == "existing"

    def test_metrics_incremented_on_success(self, isolate_db):
        with (
            patch("scheduled.refresh_stats_db._load_table", side_effect=_noop_load_table),
            patch("scheduled.refresh_stats_db.stats_db_refresh_total") as mock_counter,
            patch("scheduled.refresh_stats_db.stats_db_last_refresh_timestamp") as mock_gauge,
            patch("scheduled.refresh_stats_db.reset_stats_connection"),
        ):
            refresh_stats_db()

        mock_counter.labels.assert_called_with(status="success")
        mock_counter.labels(status="success").inc.assert_called_once()
        mock_gauge.set.assert_called_once()

    def test_metrics_incremented_on_error(self, isolate_db):
        with (
            patch(
                "scheduled.refresh_stats_db._load_table",
                side_effect=Exception("fail"),
            ),
            patch("scheduled.refresh_stats_db.stats_db_refresh_total") as mock_counter,
            pytest.raises(Exception, match="fail"),
        ):
            refresh_stats_db()

        mock_counter.labels.assert_called_with(status="error")
        mock_counter.labels(status="error").inc.assert_called_once()
