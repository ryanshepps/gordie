"""Schema constants for the DuckDB stats engine."""

from pathlib import Path

MONEYPUCK_BASE_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary"
SEASONS = list(range(2020, 2026))
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "moneypuck_stats.duckdb"

SKATER_COLUMNS = [
    "playerId",
    "season",
    "name",
    "team",
    "position",
    "situation",
    "games_played",
    "icetime",
    "I_F_goals",
    "I_F_primaryAssists",
    "I_F_secondaryAssists",
    "I_F_points",
    "I_F_shotsOnGoal",
    "I_F_xGoals",
    "I_F_hits",
    "I_F_takeaways",
    "I_F_highDangerShots",
    "I_F_highDangerxGoals",
    "onIce_corsiPercentage",
    "onIce_fenwickPercentage",
    "OnIce_F_xGoals",
    "OnIce_A_xGoals",
]

TOOL_DESCRIPTION = """\
Query MoneyPuck NHL statistics stored in a local DuckDB database using SQL.

Available tables: skaters, goalies, teams
Seasons available: 2020-2025

Key skater columns:
  playerId, season, name, team, position, situation,
  games_played, icetime,
  I_F_goals, I_F_primaryAssists, I_F_secondaryAssists, I_F_points,
  I_F_shotsOnGoal, I_F_xGoals,
  I_F_hits, I_F_takeaways,
  I_F_highDangerShots, I_F_highDangerxGoals,
  onIce_corsiPercentage, onIce_fenwickPercentage,
  OnIce_F_xGoals, OnIce_A_xGoals

IMPORTANT: Most stats are split by situation. Use situation = 'all' for totals,
'5on5' for even-strength, '5on4' for power play, '4on5' for penalty kill.

Example queries:
  -- Top 5 goal scorers this season (all situations)
  SELECT name, team, I_F_goals
  FROM skaters
  WHERE situation = 'all' AND season = 2025
  ORDER BY I_F_goals DESC
  LIMIT 5

  -- Players who scored 30+ goals in each of the last 3 seasons
  SELECT name
  FROM skaters
  WHERE situation = 'all' AND season >= 2023 AND I_F_goals >= 30
  GROUP BY name
  HAVING COUNT(DISTINCT season) = 3

  -- Team xGoals comparison this season
  SELECT team, SUM(I_F_xGoals) as total_xGoals
  FROM skaters
  WHERE situation = '5on5' AND season = 2025
  GROUP BY team
  ORDER BY total_xGoals DESC
"""
