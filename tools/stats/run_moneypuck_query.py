"""Tool for querying MoneyPuck NHL statistics via the moneypuckpy CLI."""

import shlex
import subprocess

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)

try:
    _cli_help = subprocess.run(
        ["uv", "run", "moneypuckpy", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout
except Exception:
    _cli_help = "(CLI help unavailable)"

_TOOL_DESCRIPTION = f"""\
Query MoneyPuck NHL statistics using the moneypuckpy CLI.

Available commands and flags:

search <name> [--json]
    Search for a player by name.

player bio <name>
    Get player biography.

player stats <name> [--season YEAR] [--situation all|5on5|5on4|4on5] [--game-type regular|playoffs] [--json]
    Get player season stats. Includes xGoals, Fenwick%, Corsi%, TOI, goals, assists, etc.

player career <name> [--game-type regular|playoffs] [--json]
    Get player career stats across all seasons.

player gamelog <name> [--game-type regular|playoffs] [--json]
    Get player game-by-game log for current season.

goalie stats <name> [--season YEAR] [--situation all|5on5|5on4|4on5] [--game-type regular|playoffs] [--json]
    Get goalie season stats.

goalie career <name> [--game-type regular|playoffs] [--json]
    Get goalie career stats.

team stats [--season YEAR] [--situation all|5on5|5on4|4on5] [--game-type regular|playoffs] [--team ABBREV] [--json]
    Get team stats. Use --team to filter to a specific team.

schema
    Show the full list of available stat columns.

IMPORTANT: Always pass --json for structured output.

Examples:
    "player stats 'Connor McDavid' --json"
    "player career 'Sidney Crosby' --json"
    "player gamelog 'Auston Matthews' --json"
    "goalie stats 'Connor Hellebuyck' --json"
    "team stats --team TOR --json"
    "search 'McDavid' --json"

Full CLI help:
{_cli_help}"""


class RunMoneypuckQueryInput(BaseModel):
    """Input schema for run_moneypuck_query tool."""

    command: str = Field(
        description="The moneypuckpy CLI command to run (without the 'moneypuckpy' prefix)"
    )


@tool(args_schema=RunMoneypuckQueryInput, description=_TOOL_DESCRIPTION)
def run_moneypuck_query(command: str) -> str:
    """Query MoneyPuck NHL statistics using the moneypuckpy CLI."""
    try:
        args = ["uv", "run", "moneypuckpy", *shlex.split(command)]
        logger.info(f"Running moneypuckpy command: {' '.join(args)}")

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.stderr:
            logger.warning(f"moneypuckpy stderr: {result.stderr}")

        if result.returncode != 0:
            return f"Command failed (exit code {result.returncode}): {result.stderr or result.stdout}"

        return result.stdout

    except subprocess.TimeoutExpired:
        logger.error(f"moneypuckpy command timed out: {command}")
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        logger.error(f"Error running moneypuckpy: {e}")
        return f"Error running moneypuckpy: {e}"
