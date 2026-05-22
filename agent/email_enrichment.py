"""Email enrichment middleware for adding player statistics tables.

This module extracts player names mentioned in email content,
fetches their MoneyPuck statistics, and appends a formatted table.
"""

import re
from typing import Any

from client.moneypuck_cli import StatValue, get_player_stats_by_names, search_player
from module.logger import get_logger

logger = get_logger(__name__)


def _to_int(val: StatValue, default: int = 0) -> int:
    if val is None or val is True or val is False:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_float(val: StatValue, default: float = 0.0) -> float:
    if val is None or val is True or val is False:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# Stats to include in the table (subset for readability)
TABLE_STATS = [
    ("name", "Player"),
    ("position", "Pos"),
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
]


def extract_and_validate_player_names(content: str) -> list[tuple[str, int]]:
    """Extract player names from content and validate against database.

    Uses regex to find "First Last" patterns, then validates each
    against the MoneyPuck player database via O(1) lookup.

    Args:
        content: The email message content

    Returns:
        List of (canonical_name, player_id) tuples for valid players
    """
    # Pattern for "First Last" names (capitalized words)
    # Matches: Connor McDavid, Auston Matthews, etc.
    full_name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"

    # Find all matches
    matches = re.findall(full_name_pattern, content)

    if not matches:
        return []

    seen: set[str] = set()
    validated: list[tuple[str, int]] = []

    for name in matches:
        name_lower = name.lower()
        if name_lower in seen:
            continue
        seen.add(name_lower)

        results = search_player(name)
        if results:
            first = results[0]
            canonical_name = str(first.get("name", name))
            player_id = int(first.get("player_id", first.get("playerId", 0)))
            if player_id:
                validated.append((canonical_name, player_id))

    return validated


def fetch_player_stats(player_names: list[str]) -> list[dict[str, Any]]:
    """Fetch MoneyPuck stats for players by name via CLI.

    Args:
        player_names: List of player names

    Returns:
        List of formatted player stat dicts
    """
    if not player_names:
        return []

    try:
        all_stats = get_player_stats_by_names(player_names)

        stats_list: list[dict[str, Any]] = []
        for name, stats in all_stats.items():
            goals = _to_int(stats.get("goals") or stats.get("I_F_goals"))
            points = _to_int(stats.get("points") or stats.get("I_F_points"))
            assists = max(0, points - goals)
            x_goals = _to_float(stats.get("x_goals") or stats.get("I_F_xGoals"))

            stats_list.append(
                {
                    "name": str(stats.get("name") or name),
                    "position": str(stats.get("position") or ""),
                    "games_played": _to_int(stats.get("games_played")),
                    "goals": goals,
                    "assists": assists,
                    "points": points,
                    "points_per_game": round(_to_float(stats.get("points_per_game")), 2),
                    "toi_per_game_minutes": round(_to_float(stats.get("toi_per_game_minutes")), 1),
                    "x_goals": round(x_goals, 2),
                    "goals_above_expected": round(goals - x_goals, 2),
                    "fenwick_pct": round(
                        _to_float(stats.get("fenwick_pct") or stats.get("onIce_fenwickPercentage")),
                        1,
                    ),
                    "corsi_pct": round(
                        _to_float(stats.get("corsi_pct") or stats.get("onIce_corsiPercentage")), 1
                    ),
                    "shots_on_goal": _to_int(
                        stats.get("shots_on_goal") or stats.get("I_F_shotsOnGoal")
                    ),
                    "high_danger_goals": _to_int(
                        stats.get("high_danger_goals") or stats.get("I_F_highDangerGoals")
                    ),
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
        "Stats: GP=Games Played, G=Goals, A=Assists, "
        "P=Points, P/GP=Points Per Game, TOI=Time On Ice (min/game), xG=Expected Goals, "
        "G-xG=Goals Above Expected, F%=Fenwick %, CF%=Corsi %, SOG=Shots On Goal, "
        "HDG=High Danger Goals"
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
) -> tuple[str, str]:
    """Extract players from email and generate stats tables.

    This is the main entry point for email enrichment. It:
    1. Extracts and validates player names against MoneyPuck database
    2. Fetches MoneyPuck statistics for matched players
    3. Returns formatted tables to append to the email

    Note: user_email and league_id are kept for API compatibility but
    are no longer used since we now use only MoneyPuck stats (no Yahoo data).

    Args:
        message_content: The email message content
        user_email: User's email (unused, kept for compatibility)
        league_id: Yahoo fantasy league ID (unused, kept for compatibility)

    Returns:
        Tuple of (markdown_table, html_table) to append to email
    """
    # Extract and validate player names against database
    player_matches = extract_and_validate_player_names(message_content)

    if not player_matches:
        logger.debug("No valid player names found in email content")
        return "", ""

    player_names = [name for name, _ in player_matches]

    logger.info(f"Found {len(player_matches)} players: {player_names}")

    stats = fetch_player_stats(player_names)

    if not stats:
        logger.debug("Could not fetch stats for any players")
        return "", ""

    logger.info(f"Fetched stats for {len(stats)} players")

    # Format tables
    markdown_table = format_stats_table_markdown(stats)
    html_table = format_stats_table_html(stats)

    return markdown_table, html_table
