"""Email enrichment middleware for adding player statistics tables.

This module extracts player names mentioned in email content,
fetches their MoneyPuck statistics, and appends a formatted table.
"""

import logging
import re
from typing import Any

from client.moneypuck_client import get_multiple_players_stats, search_players

logger = logging.getLogger(__name__)

# Common words that might be mistaken for player names
EXCLUDED_WORDS = {
    "the",
    "and",
    "for",
    "you",
    "your",
    "with",
    "from",
    "this",
    "that",
    "have",
    "has",
    "had",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "team",
    "player",
    "trade",
    "pick",
    "power",
    "play",
    "drop",
    "add",
    "roster",
    "fantasy",
    "hockey",
    "nhl",
    "league",
    "season",
    "game",
    "games",
    "week",
    "weeks",
    "points",
    "goals",
    "assists",
    "shots",
    "hits",
    "blocks",
    "saves",
    "goalie",
    "forward",
    "defenseman",
    "center",
    "wing",
    "left",
    "right",
}

# Stats to include in the table (subset for readability)
TABLE_STATS = [
    ("name", "Player"),
    ("position", "Pos"),
    ("games_played", "GP"),
    ("goals", "G"),
    ("primary_assists", "A1"),
    ("secondary_assists", "A2"),
    ("points", "P"),
    ("points_per_game", "P/GP"),
    ("x_goals", "xG"),
    ("goals_above_expected", "G-xG"),
    ("pp_toi_per_game", "PPTOI/GP"),
    ("fenwick_pct", "F%"),
]


def _search_player_by_name(name: str, season: int = 2025) -> dict[str, Any] | None:
    """Search MoneyPuck for a player by name.

    Returns player info dict with player_id if found, None otherwise.
    """
    try:
        df = search_players(name, situation="all", season=season, limit=3)
        if df.empty:
            return None

        # Take best match (first result, sorted by games played)
        row = df.iloc[0]
        return {
            "player_id": int(row["playerId"]),
            "name": str(row["name"]),
            "team": str(row["team"]) if row["team"] else None,
        }
    except Exception as e:
        logger.debug(f"Error searching for player '{name}': {e}")
        return None


def extract_player_names(content: str) -> list[str]:
    """Extract potential player names from email content.

    Uses heuristics to find capitalized name patterns that look like
    hockey player names (First Last, or just Last name).

    Args:
        content: The email message content

    Returns:
        List of potential player name strings
    """
    # Pattern for "First Last" names (capitalized words)
    # Matches: Connor McDavid, Auston Matthews, etc.
    full_name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"

    # Find all matches
    matches = re.findall(full_name_pattern, content)

    # Filter out excluded words and deduplicate
    seen = set()
    player_names = []

    for name in matches:
        name_lower = name.lower()
        # Skip if any word is in excluded list
        words = name_lower.split()
        if any(word in EXCLUDED_WORDS for word in words):
            continue
        # Skip very short names (likely false positives)
        if len(name) < 5:
            continue
        # Skip duplicates
        if name_lower in seen:
            continue
        seen.add(name_lower)
        player_names.append(name)

    return player_names


def resolve_players_to_ids(
    player_names: list[str],
    season: int = 2025,
) -> list[dict[str, Any]]:
    """Resolve player names to MoneyPuck player data.

    Args:
        player_names: List of player name strings to resolve
        season: NHL season year

    Returns:
        List of player info dicts with player_id, name, team
    """
    resolved = []
    seen_ids = set()

    for name in player_names:
        result = _search_player_by_name(name, season=season)
        if result and result["player_id"] not in seen_ids:
            resolved.append(result)
            seen_ids.add(result["player_id"])

    return resolved


def fetch_player_stats(
    player_ids: list[int],
    season: int = 2025,
) -> list[dict[str, Any]]:
    """Fetch MoneyPuck stats for a list of player IDs.

    Fetches both "all" situation stats and "5on4" (power play) stats
    to include PP time on ice.

    Args:
        player_ids: List of NHL player IDs
        season: NHL season year

    Returns:
        List of formatted player stat dicts
    """
    if not player_ids:
        return []

    try:
        # Fetch all-situation stats
        df_all = get_multiple_players_stats(player_ids, situation="all", season=season)

        # Fetch power play stats for PP TOI
        df_pp = get_multiple_players_stats(player_ids, situation="5on4", season=season)

        stats_list = []
        for player_id in player_ids:
            player_df = df_all[df_all["playerId"] == player_id]
            if player_df.empty:
                continue

            row = player_df.iloc[0]
            games = int(row.get("games_played", 0)) or 1  # Avoid division by zero
            goals = int(row.get("I_F_goals", 0))
            primary_assists = int(row.get("I_F_primaryAssists", 0))
            secondary_assists = int(row.get("I_F_secondaryAssists", 0))
            points = int(row.get("I_F_points", 0))
            x_goals = float(row.get("I_F_xGoals", 0))
            fenwick_pct = float(row.get("onIce_fenwickPercentage", 0))

            # Get PP TOI from power play stats
            pp_toi_seconds = 0.0
            pp_df = df_pp[df_pp["playerId"] == player_id]
            if not pp_df.empty:
                pp_toi_seconds = float(pp_df.iloc[0].get("icetime", 0))

            # Format PP TOI as minutes per game
            pp_toi_minutes = pp_toi_seconds / 60 if pp_toi_seconds else 0
            pp_toi_per_game = round(pp_toi_minutes / games, 2) if games > 0 else 0

            stats_list.append(
                {
                    "player_id": player_id,
                    "name": str(row.get("name", "Unknown")),
                    "position": str(row.get("position", "")),
                    "games_played": int(row.get("games_played", 0)),
                    "goals": goals,
                    "primary_assists": primary_assists,
                    "secondary_assists": secondary_assists,
                    "points": points,
                    "points_per_game": round(points / games, 2) if games > 0 else 0,
                    "x_goals": round(x_goals, 2),
                    "goals_above_expected": round(goals - x_goals, 2),
                    "pp_toi_per_game": pp_toi_per_game,
                    "fenwick_pct": round(fenwick_pct * 100, 1),
                }
            )

        return stats_list

    except Exception as e:
        logger.error(f"Error fetching player stats: {e}")
        return []


def format_stats_table_markdown(stats: list[dict[str, Any]]) -> str:
    """Format player stats as a markdown table.

    Args:
        stats: List of player stat dicts

    Returns:
        Markdown table string
    """
    if not stats:
        return ""

    # Build header
    headers = [label for _, label in TABLE_STATS]
    header_row = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"

    # Build data rows
    rows = []
    for player in stats:
        values = []
        for key, _ in TABLE_STATS:
            val = player.get(key, "")
            values.append(str(val) if val is not None else "")
        rows.append("| " + " | ".join(values) + " |")

    table = "\n".join([header_row, separator, *rows])

    return f"\n\n---\n\n**Player Statistics (via MoneyPuck)**\n\n{table}"


def format_stats_table_html(stats: list[dict[str, Any]]) -> str:
    """Format player stats as an HTML table.

    Args:
        stats: List of player stat dicts

    Returns:
        HTML table string
    """
    if not stats:
        return ""

    # Table styles
    table_style = (
        "border-collapse: collapse; width: 100%; margin-top: 20px; "
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
        "font-size: 14px;"
    )
    header_style = (
        "background-color: #f8f9fa; border: 1px solid #dee2e6; "
        "padding: 8px 12px; text-align: left; font-weight: 600;"
    )
    cell_style = "border: 1px solid #dee2e6; padding: 8px 12px; text-align: left;"

    # Build header row
    header_cells = "".join(f'<th style="{header_style}">{label}</th>' for _, label in TABLE_STATS)

    # Build data rows
    data_rows = []
    for i, player in enumerate(stats):
        row_bg = "background-color: #ffffff;" if i % 2 == 0 else "background-color: #f8f9fa;"
        cells = "".join(
            f'<td style="{cell_style} {row_bg}">{player.get(key, "")}</td>'
            for key, _ in TABLE_STATS
        )
        data_rows.append(f"<tr>{cells}</tr>")

    summary_style = "font-weight: bold; cursor: pointer; margin-bottom: 10px;"
    stats_note = (
        "Stats: GP=Games Played, G=Goals, A1=Primary Assists, A2=Secondary Assists, "
        "P=Points, P/GP=Points Per Game, xG=Expected Goals, G-xG=Goals Above Expected, "
        "PPTOI/GP=Power Play TOI Per Game (minutes), F%=Fenwick %"
    )
    return f'''
<div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ccc;">
    <details>
        <summary style="{summary_style}">Player Statistics (via MoneyPuck)</summary>
        <table style="{table_style}">
            <thead>
                <tr>{header_cells}</tr>
            </thead>
            <tbody>
                {"".join(data_rows)}
            </tbody>
        </table>
        <p style="font-size: 12px; color: #666; margin-top: 10px;">
            {stats_note}
        </p>
    </details>
</div>
'''


def enrich_email_with_player_stats(
    message_content: str,
    season: int = 2025,
) -> tuple[str, str]:
    """Extract players from email and generate stats tables.

    This is the main entry point for email enrichment. It:
    1. Extracts player names from the message content
    2. Resolves them to MoneyPuck player IDs
    3. Fetches their statistics
    4. Returns formatted tables to append to the email

    Args:
        message_content: The email message content
        season: NHL season year for stats

    Returns:
        Tuple of (markdown_table, html_table) to append to email
    """
    # Extract player names from content
    player_names = extract_player_names(message_content)

    if not player_names:
        logger.debug("No player names found in email content")
        return "", ""

    logger.info(f"Found {len(player_names)} potential player names: {player_names}")

    # Resolve to player IDs
    resolved_players = resolve_players_to_ids(player_names, season=season)

    if not resolved_players:
        logger.debug("Could not resolve any player names to IDs")
        return "", ""

    resolved_names = [p["name"] for p in resolved_players]
    logger.info(f"Resolved {len(resolved_players)} players: {resolved_names}")

    # Fetch stats
    player_ids = [p["player_id"] for p in resolved_players]
    stats = fetch_player_stats(player_ids, season=season)

    if not stats:
        logger.debug("Could not fetch stats for any players")
        return "", ""

    logger.info(f"Fetched stats for {len(stats)} players")

    # Format tables
    markdown_table = format_stats_table_markdown(stats)
    html_table = format_stats_table_html(stats)

    return markdown_table, html_table
