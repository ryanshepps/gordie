"""Tests for the refresh_stats_db job."""

from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from gordie.scheduled.refresh_stats_db import refresh_stats_db


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    test_db_path = tmp_path / "moneypuck_stats.duckdb"
    from gordie.integrations.defaults import default_plugins
    from gordie.runtime import Runtime

    monkeypatch.setenv("GORDIE_DATA_DIR", str(tmp_path))
    runtime = Runtime(default_plugins())
    with runtime.activate():
        yield test_db_path
    runtime.close()


def _fake_download_csv(url: str, dest: Path) -> None:
    dest.write_text("name,team,season\nTest Player,TST,2025\n")


class TestRefreshStatsDb:
    def test_successful_refresh_creates_db_and_resets_connection(self, isolate_db):
        with (
            patch(
                "gordie.scheduled.refresh_stats_db._download_csv", side_effect=_fake_download_csv
            ),
            patch("gordie.scheduled.refresh_stats_db.reset_stats_connection") as mock_reset,
        ):
            refresh_stats_db()

        assert isolate_db.exists()
        mock_reset.assert_called_once()

        conn = duckdb.connect(str(isolate_db), read_only=True)
        result = conn.execute("SELECT name FROM skaters LIMIT 1").fetchone()
        conn.close()
        assert result is not None
        assert result[0] == "Test Player"

    def test_failed_download_preserves_existing_db(self, isolate_db):
        isolate_db.write_text("existing")

        with (
            patch(
                "gordie.scheduled.refresh_stats_db._download_csv",
                side_effect=Exception("download failed"),
            ),
            pytest.raises(Exception, match="download failed"),
        ):
            refresh_stats_db()

        assert isolate_db.read_text() == "existing"
