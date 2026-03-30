import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import requests
from pydantic import BaseModel, Field
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from client.teams.mlb_teams import MLB_TEAMS
from module.logger import get_logger

logger = get_logger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

_ABBR_TO_ID: dict[str, int] = {}


def _ensure_team_ids() -> None:
    if _ABBR_TO_ID:
        return

    try:
        response = requests.get(f"{MLB_API_BASE}/teams?sportId=1", timeout=15)
        response.raise_for_status()
        data = response.json()

        for team in data.get("teams", []):
            abbr = team.get("abbreviation", "")
            team_id = team.get("id")
            if abbr and team_id:
                _ABBR_TO_ID[abbr] = team_id
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch MLB team IDs: {e}")


def _create_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class GetMlbTeamScheduleInput(BaseModel):
    team_abbrevs: list[str] = Field(
        description="List of MLB team abbreviations (e.g., ['NYY', 'LAD', 'HOU'])"
    )


def _parse_game(game: dict[str, Any]) -> dict[str, str | int | None]:
    game_date = game.get("gameDate", "")
    date_only = game_date[:10] if game_date else ""

    home = game.get("teams", {}).get("home", {}).get("team", {})
    away = game.get("teams", {}).get("away", {}).get("team", {})

    return {
        "game_id": game.get("gamePk"),
        "date": date_only,
        "start_time_utc": game_date,
        "away_team": away.get("abbreviation", ""),
        "home_team": home.get("abbreviation", ""),
        "venue": game.get("venue", {}).get("name", ""),
        "game_state": game.get("status", {}).get("detailedState", ""),
    }


def _fetch_team_schedule(
    team_abbrev: str, start_date: datetime, end_date: datetime, this_sunday: datetime
) -> tuple[str, dict[str, Any]]:
    team_upper = team_abbrev.upper()

    if team_upper not in MLB_TEAMS:
        return team_abbrev, {
            "status": "error",
            "message": f"Unknown team abbreviation: {team_abbrev}. Valid: {', '.join(sorted(MLB_TEAMS.keys()))}",
        }

    _ensure_team_ids()
    team_id = _ABBR_TO_ID.get(team_upper)
    if team_id is None:
        return team_abbrev, {
            "status": "error",
            "message": f"Could not resolve team ID for {team_upper}",
        }

    try:
        session = _create_session()
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        url = f"{MLB_API_BASE}/schedule?teamId={team_id}&startDate={start_str}&endDate={end_str}&sportId=1"
        response = session.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        games: list[dict[str, str | int | None]] = []
        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                games.append(_parse_game(game))

        games.sort(key=lambda g: str(g.get("date", "")))

        sunday_str = this_sunday.strftime("%Y-%m-%d")
        this_week_games = [
            g for g in games
            if str(g.get("date", "")) <= sunday_str
        ]
        next_week_games = [
            g for g in games
            if str(g.get("date", "")) > sunday_str
        ]

        result: dict[str, Any] = {
            "status": "success",
            "team_name": MLB_TEAMS[team_upper],
            "period": {"start": start_str, "end": end_str},
            "total_games": len(games),
            "this_week_games": len(this_week_games),
            "next_week_games": len(next_week_games),
            "games": games,
        }

        logger.info(
            f"{team_upper}: {len(games)} games ({len(this_week_games)} this week, {len(next_week_games)} next week)"
        )
        return team_upper, result

    except requests.RequestException as e:
        logger.error(f"Error fetching schedule for {team_upper}: {e}")
        return team_abbrev, {"status": "error", "message": f"Failed to fetch schedule: {e!s}"}
    except Exception as e:
        logger.error(f"Unexpected error for {team_upper}: {e}")
        return team_abbrev, {"status": "error", "message": f"Unexpected error: {e!s}"}


def get_mlb_team_schedule(team_abbrevs: list[str]) -> str:
    """
    Get the number of games each MLB team has for the remainder of this week and next week.

    This is useful for fantasy decisions - players on teams with more games
    have more opportunities to accumulate points.

    Args:
        team_abbrevs: List of MLB team abbreviations (e.g., ['NYY', 'LAD', 'HOU'])

    Returns:
        JSON string containing game counts and schedule details for each team
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    this_sunday = today + timedelta(days=days_until_sunday)
    next_sunday = this_sunday + timedelta(days=7)

    results: dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(
                _fetch_team_schedule, team_abbrev, today, next_sunday, this_sunday
            ): team_abbrev
            for team_abbrev in team_abbrevs
        }

        for future in as_completed(futures):
            team_abbrev, result = future.result()
            results[team_abbrev] = result

    return json.dumps(results, indent=2)
