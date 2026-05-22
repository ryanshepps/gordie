"""Internal helpers for querying MoneyPuck via the moneypuckpy CLI."""

import json
import shlex
import subprocess

from module.logger import get_logger

logger = get_logger(__name__)

StatValue = str | int | float | bool | None
PlayerStats = dict[str, StatValue]


def run_cli(command: str, timeout: int = 30) -> str:
    """Run a moneypuckpy CLI command and return stdout.

    Args:
        command: CLI args without the 'moneypuckpy' prefix
        timeout: Timeout in seconds

    Returns:
        stdout as string

    Raises:
        RuntimeError: If the command fails or times out
    """
    args = ["uv", "run", "moneypuckpy", *shlex.split(command)]
    logger.debug(f"Running: {' '.join(args)}")

    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(
            f"moneypuckpy failed (exit {result.returncode}): {result.stderr or result.stdout}"
        )

    return result.stdout


def search_player(name: str) -> list[dict[str, str | int]]:
    """Search for players by name, returning structured results.

    Args:
        name: Player name to search for

    Returns:
        List of dicts with player_id, name, team, position, games_played
    """
    try:
        output = run_cli(f"search {shlex.quote(name)} --json")
        return json.loads(output)
    except (RuntimeError, json.JSONDecodeError) as e:
        logger.error(f"Player search failed for '{name}': {e}")
        return []


def get_player_stats(name: str, situation: str = "all") -> PlayerStats:
    """Get season stats for a player by name.

    Args:
        name: Player name
        situation: Situation filter (all, 5on5, 5on4, 4on5)

    Returns:
        Dict of player stats, or empty dict on failure
    """
    try:
        output = run_cli(f"player stats {shlex.quote(name)} --situation {situation} --json")
        return json.loads(output)
    except (RuntimeError, json.JSONDecodeError) as e:
        logger.error(f"Player stats failed for '{name}': {e}")
        return {}


def get_player_stats_by_names(names: list[str], situation: str = "all") -> dict[str, PlayerStats]:
    """Get season stats for multiple players by name.

    Args:
        names: List of player names
        situation: Situation filter

    Returns:
        Dict mapping player name to their stats dict
    """
    results: dict[str, PlayerStats] = {}
    for name in names:
        stats = get_player_stats(name, situation)
        if stats:
            results[name] = stats
    return results
