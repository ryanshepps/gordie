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

## Data model

Each row is one player + one season + one situation. A player who played 3 seasons
has 3 rows (per situation). Stats on each row are already season totals — never SUM
a stat across seasons unless you genuinely want a multi-season total.

The situation filter is enforced automatically via the required 'situation' parameter.
Do NOT add a situation filter in your SQL — it is injected for you.

## Query patterns

PER-SEASON THRESHOLDS ("scored 30+ goals in each of N seasons"):
  Filter rows with WHERE, then GROUP BY name HAVING COUNT(DISTINCT season) = N.
  Do NOT use SUM — the WHERE clause already filters each season's row individually.

  SELECT name FROM skaters
  WHERE season >= 2023 AND I_F_goals >= 30
  GROUP BY name HAVING COUNT(DISTINCT season) = 3

MULTI-SEASON TOTALS ("total goals over 3 seasons"):
  Use SUM with GROUP BY. Only appropriate when the user wants a combined total.

  SELECT name, SUM(I_F_goals) as total_goals FROM skaters
  WHERE season IN (2023, 2024, 2025)
  GROUP BY name ORDER BY total_goals DESC

SINGLE-SEASON STATS:
  No aggregation needed — each row is already a season total.

  SELECT name, team, I_F_goals FROM skaters
  WHERE season = 2025
  ORDER BY I_F_goals DESC LIMIT 5

## Rules

- Write ONE query that answers the question. Never run multiple overlapping queries
  and combine the results yourself — this leads to incorrect totals.
- When the user says "more than X each season" or "in every season", use the
  per-season threshold pattern (WHERE + HAVING COUNT), not SUM.
- Present only the data the query returns. If results are empty, say no players
  matched — never fill in numbers from memory.
"""
