"""Tool to get player line information and linemates from NHL API shift data."""

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import requests
from nhlpy import NHLClient
from pydantic import BaseModel, Field
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from module.logger import get_logger

logger = get_logger(__name__)

NHL_API_BASE = "https://api-web.nhle.com"


def _get_session() -> requests.Session:
    """Create a requests session with retry logic and connection pooling."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class GetPlayerLineInfoInput(BaseModel):
    """Input schema for get_player_line_info tool."""

    player_ids: list[int] = Field(
        description="List of NHL API player IDs to get line information for"
    )


def _time_to_seconds(time_str: str | None) -> int:
    """Convert MM:SS time string to seconds.

    Args:
        time_str: Time in MM:SS format

    Returns:
        Time in seconds, or 0 if invalid
    """
    if not time_str:
        return 0
    try:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def _get_recent_game_id(team_abbrev: str) -> int | None:
    """Get the most recent completed game ID for a team.

    Args:
        team_abbrev: Three-letter team abbreviation

    Returns:
        Game ID or None if no recent game found
    """
    client = NHLClient()

    # Check the last 7 days for games
    for days_ago in range(1, 8):
        date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        try:
            schedule = client.schedule.daily_schedule(date=date)
            for game in schedule.get("games", []):
                if game.get("gameState") == "OFF":  # Completed game
                    away = game.get("awayTeam", {}).get("abbrev", "")
                    home = game.get("homeTeam", {}).get("abbrev", "")
                    if team_abbrev in (away, home):
                        return game["id"]
        except Exception as e:
            logger.warning(f"Error fetching schedule for {date}: {e}")
            continue

    return None


def _get_player_team(
    player_id: int, session: requests.Session | None = None
) -> tuple[str | None, str | None]:
    """Get the team abbreviation and player name for a player.

    Args:
        player_id: NHL API player ID
        session: Optional requests session with retry logic

    Returns:
        Tuple of (team_abbrev, player_name) or (None, None) if not found
    """
    try:
        url = f"{NHL_API_BASE}/v1/player/{player_id}/landing"
        response = session.get(url, timeout=15) if session else requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        team = data.get("currentTeamAbbrev")
        first_name = data.get("firstName", {}).get("default", "")
        last_name = data.get("lastName", {}).get("default", "")
        player_name = f"{first_name} {last_name}".strip()
        return team, player_name
    except Exception as e:
        logger.warning(f"Could not get team for player {player_id}: {e}")
        return None, None


def _get_team_roster_positions(team_abbrev: str) -> dict[int, dict[str, Any]]:
    """Get roster with positions for a team.

    Args:
        team_abbrev: Three-letter team abbreviation

    Returns:
        Dict mapping player_id to player info (name, position)
    """
    client = NHLClient()
    season = (
        f"{datetime.now().year}{datetime.now().year + 1}"
        if datetime.now().month >= 10
        else f"{datetime.now().year - 1}{datetime.now().year}"
    )

    try:
        roster = client.teams.team_roster(team_abbr=team_abbrev, season=season)
    except Exception as e:
        logger.warning(f"Could not get roster for {team_abbrev}: {e}")
        return {}

    players = {}

    for group in ["forwards", "defensemen", "goalies"]:
        for player in roster.get(group, []):
            player_id = player.get("id")
            first_name = player.get("firstName", {}).get("default", "")
            last_name = player.get("lastName", {}).get("default", "")
            players[player_id] = {
                "name": f"{first_name} {last_name}",
                "position": player.get("positionCode"),
                "position_group": group,
            }

    return players


def _analyze_shifts_for_linemates(
    shifts: list[dict[str, Any]],
    target_player_id: int,
    roster: dict[int, dict[str, Any]],
    target_player_name: str | None = None,
) -> dict[str, Any]:
    """Analyze shift data to find linemates for a target player.

    Args:
        shifts: List of shift data from NHL API
        target_player_id: The player to find linemates for
        roster: Dict mapping player_id to player info
        target_player_name: The name of the target player (for validation)

    Returns:
        Dict with linemate analysis
    """
    # Get position group for target player
    target_info = roster.get(target_player_id, {})
    target_position_group = target_info.get("position_group", "forwards")

    # Use provided name if roster doesn't have it
    if not target_info.get("name") and target_player_name:
        target_info = {**target_info, "name": target_player_name}

    # Filter to same team and position group
    target_team = None
    for shift in shifts:
        if shift.get("playerId") == target_player_id:
            target_team = shift.get("teamAbbrev")
            break

    if not target_team:
        return {"error": "Player not found in shift data"}

    # Build time-based overlap analysis
    # For each period, track who was on ice during each second
    period_ice_time: dict[int, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))

    for shift in shifts:
        if shift.get("teamAbbrev") != target_team:
            continue

        player_id = shift.get("playerId")
        period = shift.get("period")
        start = _time_to_seconds(shift.get("startTime", "0:00"))
        end = _time_to_seconds(shift.get("endTime", "0:00"))

        if player_id is None or period is None:
            continue

        # Track each second this player was on ice
        for second in range(start, end + 1):
            period_ice_time[period][second].add(player_id)

    # Count co-occurrence with target player
    co_occurrence: dict[int, int] = defaultdict(int)
    target_ice_time = 0

    for _period, seconds_data in period_ice_time.items():
        for _second, players_on_ice in seconds_data.items():
            if target_player_id in players_on_ice:
                target_ice_time += 1
                for other_player in players_on_ice:
                    if other_player != target_player_id:
                        co_occurrence[other_player] += 1

    # Filter to same position group and sort by co-occurrence
    # Explicitly exclude target player from linemates list (by ID and name)
    target_name = target_info.get("name", "")
    linemates = []
    for player_id, shared_seconds in co_occurrence.items():
        if player_id == target_player_id:
            continue
        player_info = roster.get(player_id, {})
        linemate_name = player_info.get("name", "Unknown")
        # Skip if this is the target player (by name match as fallback)
        if target_name and linemate_name == target_name:
            continue
        if player_info.get("position_group") == target_position_group:
            linemates.append(
                {
                    "player_id": player_id,
                    "name": linemate_name,
                    "position": player_info.get("position"),
                    "shared_ice_time_seconds": shared_seconds,
                    "shared_ice_time_pct": round(shared_seconds / target_ice_time * 100, 1)
                    if target_ice_time > 0
                    else 0,
                }
            )

    # Sort by shared ice time
    linemates.sort(key=lambda x: x["shared_ice_time_seconds"], reverse=True)

    # Determine likely line based on top linemates
    # For forwards: top 2 are likely linemates
    # For defensemen: top 1 is likely partner
    primary_linemates = linemates[:2] if target_position_group == "forwards" else linemates[:1]

    # Estimate line number based on ice time ranking
    # Get all players in same position group and rank by total ice time
    position_ice_times = []
    for player_id, info in roster.items():
        if info.get("position_group") == target_position_group:
            total_ice = 0
            for shift in shifts:
                if shift.get("playerId") == player_id:
                    duration = shift.get("duration", "0:00")
                    total_ice += _time_to_seconds(duration)
            if total_ice > 0:
                position_ice_times.append((player_id, total_ice))

    position_ice_times.sort(key=lambda x: x[1], reverse=True)

    # Determine line number
    line_number = None
    for rank, (player_id, _) in enumerate(position_ice_times):
        if player_id == target_player_id:
            # 3 forwards per line, 2 defensemen per pairing
            divisor = 3 if target_position_group == "forwards" else 2
            line_number = (rank // divisor) + 1
            break

    return {
        "target_player": {
            "player_id": target_player_id,
            "name": target_info.get("name", "Unknown"),
            "position": target_info.get("position"),
            "position_group": target_position_group,
        },
        "estimated_line_number": line_number,
        "primary_linemates": primary_linemates,
        "all_linemates_by_ice_time": linemates[:6],  # Top 6 for context
        "target_ice_time_seconds": target_ice_time,
    }


def _process_single_player(player_id: int, session: requests.Session) -> tuple[int, dict[str, Any]]:
    """Process a single player and return their line info.

    Args:
        player_id: NHL API player ID
        session: Requests session with retry logic

    Returns:
        Tuple of (player_id, result_dict)
    """
    client = NHLClient()

    try:
        logger.info(f"Getting line info for player {player_id}")

        # Get player's team
        team_abbrev, player_name = _get_player_team(player_id, session)
        if not team_abbrev:
            return player_id, {
                "status": "error",
                "message": f"Could not determine team for player {player_id}",
            }

        # Get most recent game
        game_id = _get_recent_game_id(team_abbrev)
        if not game_id:
            return player_id, {
                "status": "error",
                "message": f"No recent completed game found for team {team_abbrev}",
            }

        logger.info(f"Using game {game_id} for player {player_id} ({team_abbrev})")

        # Get roster for position info
        roster = _get_team_roster_positions(team_abbrev)

        # Get shift data
        shift_data = client.game_center.shift_chart_data(str(game_id))
        shifts = shift_data.get("data", [])

        if not shifts:
            return player_id, {
                "status": "error",
                "message": f"No shift data available for game {game_id}",
            }

        # Analyze linemates
        analysis = _analyze_shifts_for_linemates(shifts, player_id, roster, player_name)

        if "error" in analysis:
            return player_id, {
                "status": "error",
                "message": analysis["error"],
            }

        logger.info(
            f"Player {player_id}: Line {analysis.get('estimated_line_number')}, "
            f"linemates: {[lm['name'] for lm in analysis.get('primary_linemates', [])]}"
        )

        return player_id, {
            "status": "success",
            "team": team_abbrev,
            "game_id": game_id,
            **analysis,
        }

    except Exception as e:
        logger.error(f"Error getting line info for player {player_id}: {e}")
        return player_id, {
            "status": "error",
            "message": str(e),
        }


def get_player_line_info(player_ids: list[int]) -> str:
    """
    Get line information and linemates for NHL players based on recent game shift data.

    This tool analyzes shift chart data from a player's most recent game to determine:
    - What line/pairing the player is on (1st, 2nd, 3rd, 4th)
    - Who their primary linemates are (wingers for centers, or defense partners)
    - Shared ice time percentages with linemates

    This is useful for fantasy to understand a player's role and whether they
    play with high-quality linemates who can help drive production.

    Args:
        player_ids: List of NHL API player IDs to get line information for

    Returns:
        JSON string containing line information for each player
    """
    results = {}
    session = _get_session()

    # Process players concurrently for better performance
    with ThreadPoolExecutor(max_workers=min(len(player_ids), 5)) as executor:
        futures = {
            executor.submit(_process_single_player, player_id, session): player_id
            for player_id in player_ids
        }

        for future in as_completed(futures):
            player_id, result = future.result()
            results[str(player_id)] = result

    return json.dumps(results, indent=2)
