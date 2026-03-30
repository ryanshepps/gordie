import os
import tempfile
import time
from pathlib import Path

import duckdb
import pandas as pd
from pybaseball import batting_stats, pitching_stats, team_batting, team_pitching

from module.logger import get_logger
from module.metrics import mlb_stats_db_last_refresh_timestamp, mlb_stats_db_refresh_total
from tools.mlb.stats.mlb_connection import reset_mlb_stats_connection
from tools.mlb.stats.mlb_schema import MLB_DB_PATH, MLB_SEASONS

logger = get_logger(__name__)


def _fetch_batting(season: int) -> pd.DataFrame:
    df = batting_stats(season, qual=1)
    df["Season"] = season
    return df


def _fetch_pitching(season: int) -> pd.DataFrame:
    df = pitching_stats(season, qual=1)
    df["Season"] = season
    return df


def _fetch_team_batting(season: int) -> pd.DataFrame:
    df = team_batting(season)
    df["Season"] = season
    return df


def _fetch_team_pitching(season: int) -> pd.DataFrame:
    df = team_pitching(season)
    df["Season"] = season
    return df


def _load_dataframe(
    conn: duckdb.DuckDBPyConnection, table_name: str, df: pd.DataFrame
) -> None:
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    logger.info(f"Loaded {table_name}: {count[0] if count else 0} rows")


def refresh_mlb_stats_db() -> None:
    tmp_dir = MLB_DB_PATH.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(suffix=".duckdb", dir=tmp_dir)
    tmp_path = Path(tmp_path_str)

    try:
        os.close(fd)
        tmp_path.unlink()

        batting_frames: list[pd.DataFrame] = []
        pitching_frames: list[pd.DataFrame] = []
        team_batting_frames: list[pd.DataFrame] = []
        team_pitching_frames: list[pd.DataFrame] = []

        for season in MLB_SEASONS:
            logger.info(f"Fetching MLB data for {season}")
            batting_frames.append(_fetch_batting(season))
            pitching_frames.append(_fetch_pitching(season))
            team_batting_frames.append(_fetch_team_batting(season))
            team_pitching_frames.append(_fetch_team_pitching(season))

        all_batters = pd.concat(batting_frames, ignore_index=True)
        all_pitchers = pd.concat(pitching_frames, ignore_index=True)

        all_team_batting = pd.concat(team_batting_frames, ignore_index=True)
        all_team_pitching = pd.concat(team_pitching_frames, ignore_index=True)
        all_teams = all_team_batting.merge(
            all_team_pitching,
            on=["Team", "Season"],
            suffixes=("_bat", "_pitch"),
        )

        conn = duckdb.connect(str(tmp_path))
        try:
            _load_dataframe(conn, "mlb_batters", all_batters)
            _load_dataframe(conn, "mlb_pitchers", all_pitchers)
            _load_dataframe(conn, "mlb_teams", all_teams)
        finally:
            conn.close()

        tmp_path.replace(MLB_DB_PATH)
        logger.info(f"MLB stats database refreshed at {MLB_DB_PATH}")

        reset_mlb_stats_connection()

        mlb_stats_db_refresh_total.labels(status="success").inc()
        mlb_stats_db_last_refresh_timestamp.set(time.time())

    except Exception:
        logger.exception("Failed to refresh MLB stats database")
        mlb_stats_db_refresh_total.labels(status="error").inc()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
