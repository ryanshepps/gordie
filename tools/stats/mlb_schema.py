from pathlib import Path

MLB_SEASONS = list(range(2021, 2026))
MLB_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mlb_stats.duckdb"
MLB_TABLES = ["mlb_batters", "mlb_pitchers", "mlb_teams"]

MLB_TOOL_DESCRIPTION = f"""\
Query MLB statistics stored in a local DuckDB database using SQL.
Data sourced from FanGraphs via pybaseball.

Available tables: {', '.join(MLB_TABLES)}
Seasons available: {MLB_SEASONS[0]}-{MLB_SEASONS[-1]}

IMPORTANT: Each table has a DIFFERENT schema. Do NOT assume columns from one
table exist on another. If your query fails with a column-not-found error,
the error message will include the valid columns — use those to fix your query.

## Data model

Each row is one player + one season. A player who played 3 seasons has 3 rows.
Stats on each row are already season totals — never SUM a stat across seasons
unless you genuinely want a multi-season total.

There is NO situation filter for baseball — queries run directly against the tables.

## Key columns

mlb_batters: Name, Team, Season, G, AB, PA, H, HR, R, RBI, SB, BB, SO,
  AVG, OBP, SLG, OPS, wOBA, xwOBA, Barrel%, HardHit%, BB%, K%, WAR

mlb_pitchers: Name, Team, Season, W, L, ERA, G, GS, IP, SO, BB, WHIP,
  K/9, BB/9, FIP, xFIP, xERA, Barrel%, HardHit%, WAR

mlb_teams: Team, Season (plus combined batting and pitching team stats)

## Query patterns

PER-SEASON THRESHOLDS ("hit 30+ HR in each of N seasons"):
  Filter rows with WHERE, then GROUP BY Name HAVING COUNT(DISTINCT Season) = N.
  Do NOT use SUM — the WHERE clause already filters each season's row individually.

  SELECT Name FROM mlb_batters
  WHERE Season >= 2023 AND HR >= 30
  GROUP BY Name HAVING COUNT(DISTINCT Season) = 3

MULTI-SEASON TOTALS ("total home runs over 3 seasons"):
  Use SUM with GROUP BY. Only appropriate when the user wants a combined total.

  SELECT Name, SUM(HR) as total_hr FROM mlb_batters
  WHERE Season IN (2023, 2024, 2025)
  GROUP BY Name ORDER BY total_hr DESC

SINGLE-SEASON STATS:
  No aggregation needed — each row is already a season total.

  SELECT Name, Team, HR, AVG, OPS FROM mlb_batters
  WHERE Season = 2025
  ORDER BY HR DESC LIMIT 5

## Rules

- Write ONE query that answers the question. Never run multiple overlapping queries
  and combine the results yourself — this leads to incorrect totals.
- When the user says "more than X each season" or "in every season", use the
  per-season threshold pattern (WHERE + HAVING COUNT), not SUM.
- Present only the data the query returns. If results are empty, say no players
  matched — never fill in numbers from memory.
- Column names are case-sensitive. Use the exact casing shown above.
"""
