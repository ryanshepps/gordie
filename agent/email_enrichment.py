"""Email enrichment middleware for adding player statistics tables.

This module extracts player names mentioned in email content,
fetches their MoneyPuck statistics, and appends a formatted table.
"""

import json
import logging
import re
from typing import Any

from tools.player_comparison.get_comprehensive_player_stats import (
    get_comprehensive_player_stats_internal,
)

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
    ("estimated_line_number", "Line"),
    ("games_played", "GP"),
    ("goals", "G"),
    ("assists", "A"),
    ("points", "P"),
    ("points_per_game", "P/GP"),
    ("toi_per_game_minutes", "TOI"),
    ("x_goals", "xG"),
    ("goals_above_expected", "G-xG"),
    ("fenwick_pct", "F%"),
    ("corsi_pct", "CF%"),
    ("shots_on_goal", "SOG"),
    ("high_danger_goals", "HDG"),
    ("yahoo_rank", "Rank"),
]


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


def fetch_player_stats(
    player_names: list[str],
    user_email: str,
    league_id: str,
    season: int = 2025,
) -> list[dict[str, Any]]:
    """Fetch comprehensive stats for players using the consolidated stats tool.

    Args:
        player_names: List of player names to fetch stats for
        user_email: User's email for Yahoo OAuth
        league_id: Yahoo fantasy league ID
        season: NHL season year

    Returns:
        List of formatted player stat dicts
    """
    if not player_names:
        return []

    try:
        # Use comprehensive stats tool
        response = get_comprehensive_player_stats_internal(
            player_names=player_names,
            user_email=user_email,
            league_id=league_id,
            situation="all",
            season=season,
        )
        data = json.loads(response)

        # Check for top-level error
        if data.get("status") == "error":
            logger.error(f"Comprehensive stats error: {data.get('error')}")
            return []

        stats_list = []
        for player_name, player_data in data.items():
            if player_data.get("status") != "success":
                logger.debug(f"Skipping {player_name}: {player_data.get('error', 'unknown error')}")
                continue

            # Format line number for display (None -> "-")
            line_num = player_data.get("estimated_line_number")
            line_display = str(line_num) if line_num is not None else "-"

            # Format yahoo rank (None -> "-")
            yahoo_rank = player_data.get("yahoo_rank")
            rank_display = str(yahoo_rank) if yahoo_rank is not None else "-"

            stats_list.append(
                {
                    "name": player_data.get("name", player_name),
                    "position": player_data.get("position", ""),
                    "estimated_line_number": line_display,
                    "games_played": player_data.get("games_played", 0),
                    "goals": player_data.get("goals", 0),
                    "assists": player_data.get("assists", 0),
                    "points": player_data.get("points", 0),
                    "points_per_game": round(player_data.get("points_per_game", 0), 2),
                    "toi_per_game_minutes": round(player_data.get("toi_per_game_minutes", 0), 1),
                    "x_goals": round(player_data.get("x_goals", 0), 2),
                    "goals_above_expected": round(player_data.get("goals_above_expected", 0), 2),
                    "fenwick_pct": round(player_data.get("fenwick_pct", 0), 1),
                    "corsi_pct": round(player_data.get("corsi_pct", 0), 1),
                    "shots_on_goal": player_data.get("shots_on_goal", 0),
                    "high_danger_goals": player_data.get("high_danger_goals", 0),
                    "yahoo_rank": rank_display,
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
        "Stats: Line=Estimated Line #, GP=Games Played, G=Goals, A=Assists, "
        "P=Points, P/GP=Points Per Game, TOI=Time On Ice (min/game), xG=Expected Goals, "
        "G-xG=Goals Above Expected, F%=Fenwick %, CF%=Corsi %, SOG=Shots On Goal, "
        "HDG=High Danger Goals, Rank=Yahoo Season Rank"
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
    user_email: str,
    league_id: str,
    season: int = 2025,
) -> tuple[str, str]:
    """Extract players from email and generate stats tables.

    This is the main entry point for email enrichment. It:
    1. Extracts player names from the message content
    2. Fetches comprehensive statistics (MoneyPuck, Yahoo rank, line info)
    3. Returns formatted tables to append to the email

    Args:
        message_content: The email message content
        user_email: User's email for Yahoo OAuth
        league_id: Yahoo fantasy league ID
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

    # Fetch comprehensive stats directly using player names
    stats = fetch_player_stats(
        player_names=player_names,
        user_email=user_email,
        league_id=league_id,
        season=season,
    )

    if not stats:
        logger.debug("Could not fetch stats for any players")
        return "", ""

    logger.info(f"Fetched stats for {len(stats)} players")

    # Format tables
    markdown_table = format_stats_table_markdown(stats)
    html_table = format_stats_table_html(stats)

    return markdown_table, html_table
