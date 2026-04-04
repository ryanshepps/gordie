from unittest.mock import patch

import duckdb
import pandas as pd
import pytest

from scheduled.refresh_mlb_stats_db import refresh_mlb_stats_db


def _fake_batting(season: int, **_kwargs: object) -> pd.DataFrame:
    return pd.DataFrame({"Name": ["Mike Trout"], "Team": ["LAA"], "HR": [30]})


def _fake_pitching(season: int, **_kwargs: object) -> pd.DataFrame:
    return pd.DataFrame({"Name": ["Shohei Ohtani"], "Team": ["LAD"], "ERA": [2.50]})


def _fake_team_batting(season: int, **_kwargs: object) -> pd.DataFrame:
    return pd.DataFrame({"Team": ["LAA"], "R": [700]})


def _fake_team_pitching(season: int, **_kwargs: object) -> pd.DataFrame:
    return pd.DataFrame({"Team": ["LAA"], "ERA": [3.80]})


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    test_db_path = tmp_path / "mlb_stats.duckdb"
    monkeypatch.setattr("scheduled.refresh_mlb_stats_db.MLB_DB_PATH", test_db_path)
    monkeypatch.setattr("tools.mlb.stats.mlb_connection.MLB_DB_PATH", test_db_path)
    return test_db_path


class TestRefreshMlbStatsDb:
    def test_successful_refresh_creates_db_with_three_tables(self, isolate_db):
        with (
            patch("scheduled.refresh_mlb_stats_db.batting_stats", side_effect=_fake_batting),
            patch("scheduled.refresh_mlb_stats_db.pitching_stats", side_effect=_fake_pitching),
            patch("scheduled.refresh_mlb_stats_db.team_batting", side_effect=_fake_team_batting),
            patch("scheduled.refresh_mlb_stats_db.team_pitching", side_effect=_fake_team_pitching),
            patch("scheduled.refresh_mlb_stats_db.reset_mlb_stats_connection") as mock_reset,
        ):
            refresh_mlb_stats_db()

        assert isolate_db.exists()
        mock_reset.assert_called_once()

        conn = duckdb.connect(str(isolate_db), read_only=True)
        tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
        conn.close()

        assert "mlb_batters" in tables
        assert "mlb_pitchers" in tables
        assert "mlb_teams" in tables

    def test_batters_table_has_season_column(self, isolate_db):
        with (
            patch("scheduled.refresh_mlb_stats_db.batting_stats", side_effect=_fake_batting),
            patch("scheduled.refresh_mlb_stats_db.pitching_stats", side_effect=_fake_pitching),
            patch("scheduled.refresh_mlb_stats_db.team_batting", side_effect=_fake_team_batting),
            patch("scheduled.refresh_mlb_stats_db.team_pitching", side_effect=_fake_team_pitching),
            patch("scheduled.refresh_mlb_stats_db.reset_mlb_stats_connection"),
        ):
            refresh_mlb_stats_db()

        conn = duckdb.connect(str(isolate_db), read_only=True)
        result = conn.execute("SELECT Season FROM mlb_batters LIMIT 1").fetchone()
        conn.close()
        assert result is not None

    def test_failed_fetch_preserves_existing_db(self, isolate_db):
        isolate_db.write_text("existing")

        with (
            patch(
                "scheduled.refresh_mlb_stats_db.batting_stats",
                side_effect=Exception("fetch failed"),
            ),
            pytest.raises(RuntimeError, match="No MLB data fetched for any season"),
        ):
            refresh_mlb_stats_db()

        assert isolate_db.read_text() == "existing"

    def test_metrics_incremented_on_success(self, isolate_db):
        with (
            patch("scheduled.refresh_mlb_stats_db.batting_stats", side_effect=_fake_batting),
            patch("scheduled.refresh_mlb_stats_db.pitching_stats", side_effect=_fake_pitching),
            patch("scheduled.refresh_mlb_stats_db.team_batting", side_effect=_fake_team_batting),
            patch("scheduled.refresh_mlb_stats_db.team_pitching", side_effect=_fake_team_pitching),
            patch("scheduled.refresh_mlb_stats_db.mlb_stats_db_refresh_total") as mock_counter,
            patch("scheduled.refresh_mlb_stats_db.mlb_stats_db_last_refresh_timestamp") as mock_gauge,
            patch("scheduled.refresh_mlb_stats_db.reset_mlb_stats_connection"),
        ):
            refresh_mlb_stats_db()

        mock_counter.labels.assert_called_with(status="success")
        mock_counter.labels(status="success").inc.assert_called_once()
        mock_gauge.set.assert_called_once()

    def test_metrics_incremented_on_error(self, isolate_db):
        with (
            patch(
                "scheduled.refresh_mlb_stats_db.batting_stats",
                side_effect=Exception("fail"),
            ),
            patch("scheduled.refresh_mlb_stats_db.mlb_stats_db_refresh_total") as mock_counter,
            pytest.raises(RuntimeError, match="No MLB data fetched for any season"),
        ):
            refresh_mlb_stats_db()

        mock_counter.labels.assert_called_with(status="error")
        mock_counter.labels(status="error").inc.assert_called_once()

    def test_team_table_merges_batting_and_pitching(self, isolate_db):
        with (
            patch("scheduled.refresh_mlb_stats_db.batting_stats", side_effect=_fake_batting),
            patch("scheduled.refresh_mlb_stats_db.pitching_stats", side_effect=_fake_pitching),
            patch("scheduled.refresh_mlb_stats_db.team_batting", side_effect=_fake_team_batting),
            patch("scheduled.refresh_mlb_stats_db.team_pitching", side_effect=_fake_team_pitching),
            patch("scheduled.refresh_mlb_stats_db.reset_mlb_stats_connection"),
        ):
            refresh_mlb_stats_db()

        conn = duckdb.connect(str(isolate_db), read_only=True)
        cols = [row[0] for row in conn.execute("DESCRIBE mlb_teams").fetchall()]
        conn.close()

        assert "Team" in cols
        assert "R" in cols
        assert "ERA" in cols
