"""Tool to fetch NHL team schedules for the current and next week."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from module.logger import get_logger

logger = get_logger(__name__)

# NHL API base URL
NHL_API_BASE = "https://api-web.nhle.com"

# NHL team abbreviations
NHL_TEAMS = {
    "ANA": "Anaheim Ducks",
    "ARI": "Arizona Coyotes",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CAR": "Carolina Hurricanes",
    "CBJ": "Columbus Blue Jackets",
    "CGY": "Calgary Flames",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NJD": "New Jersey Devils",
    "NSH": "Nashville Predators",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SEA": "Seattle Kraken",
    "SJS": "San Jose Sharks",
    "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "UTA": "Utah Hockey Club",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WPG": "Winnipeg Jets",
    "WSH": "Washington Capitals",
}


def _create_session() -> requests.Session:
    """Create a requests session with retry logic."""
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


class GetTeamScheduleInput(BaseModel):
    """Input schema for get_team_schedule tool."""

    team_abbrevs: list[str] = Field(
        description="List of NHL team abbreviations (e.g., ['TOR', 'BOS', 'EDM'])"
    )


def _get_month_schedule(
    session: requests.Session, team_abbrev: str, year_month: str
) -> list[dict[str, Any]]:
    """Fetch the monthly schedule for a team.

    Args:
        session: Requests session with retry logic
        team_abbrev: Three-letter NHL team abbreviation
        year_month: Year and month in YYYY-MM format

    Returns:
        List of game dictionaries
    """
    url = f"{NHL_API_BASE}/v1/club-schedule/{team_abbrev}/month/{year_month}"
    response = session.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data.get("games", [])


def _parse_game(game: dict[str, Any]) -> dict[str, Any]:
    """Parse a game object into a simplified format.

    Args:
        game: Raw game data from NHL API

    Returns:
        Simplified game dictionary
    """
    game_date = game.get("gameDate", "")
    start_time = game.get("startTimeUTC", "")

    away_team = game.get("awayTeam", {})
    home_team = game.get("homeTeam", {})

    return {
        "game_id": game.get("id"),
        "date": game_date,
        "start_time_utc": start_time,
        "away_team": away_team.get("abbrev", ""),
        "home_team": home_team.get("abbrev", ""),
        "venue": game.get("venue", {}).get("default", ""),
        "game_state": game.get("gameState", ""),
    }


def _get_games_for_period(
    session: requests.Session, team_abbrev: str, start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Get all games for a team within a date range using monthly endpoint.

    Args:
        session: Requests session with retry logic
        team_abbrev: Three-letter NHL team abbreviation
        start_date: Start of the period
        end_date: End of the period

    Returns:
        List of games within the period
    """
    games = []
    seen_game_ids = set()

    # Determine which months we need to fetch
    months_to_fetch = set()
    current = start_date.replace(day=1)
    while current <= end_date:
        months_to_fetch.add(current.strftime("%Y-%m"))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    for year_month in sorted(months_to_fetch):
        try:
            month_games = _get_month_schedule(session, team_abbrev, year_month)
            for game in month_games:
                game_id = game.get("id")
                if game_id and game_id not in seen_game_ids:
                    game_date_str = game.get("gameDate", "")
                    if game_date_str:
                        game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
                        if start_date <= game_date <= end_date:
                            games.append(_parse_game(game))
                            seen_game_ids.add(game_id)
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch schedule for {team_abbrev} month {year_month}: {e}")

    return sorted(games, key=lambda g: g["date"])


def _fetch_team_schedule(
    team_abbrev: str, today: datetime, next_sunday: datetime, this_sunday: datetime
) -> tuple[str, dict[str, Any]]:
    """Fetch schedule for a single team. Used for concurrent execution.

    Args:
        team_abbrev: Three-letter NHL team abbreviation
        today: Start date
        next_sunday: End date
        this_sunday: Dividing date between this week and next week

    Returns:
        Tuple of (team_abbrev, result_dict)
    """
    team_upper = team_abbrev.upper()

    if team_upper not in NHL_TEAMS:
        return team_abbrev, {
            "status": "error",
            "message": f"Unknown team abbreviation: {team_abbrev}. Valid abbreviations: {', '.join(sorted(NHL_TEAMS.keys()))}",
        }

    try:
        session = _create_session()
        logger.info(
            f"Fetching schedule for {team_upper} from {today.strftime('%Y-%m-%d')} to {next_sunday.strftime('%Y-%m-%d')}"
        )

        games = _get_games_for_period(session, team_upper, today, next_sunday)

        # Split games into this week and next week
        this_week_games = [
            g for g in games if datetime.strptime(g["date"], "%Y-%m-%d") <= this_sunday
        ]
        next_week_games = [
            g for g in games if datetime.strptime(g["date"], "%Y-%m-%d") > this_sunday
        ]

        result = {
            "status": "success",
            "team_name": NHL_TEAMS[team_upper],
            "period": {
                "start": today.strftime("%Y-%m-%d"),
                "end": next_sunday.strftime("%Y-%m-%d"),
            },
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
        return team_abbrev, {
            "status": "error",
            "message": f"Failed to fetch schedule: {e!s}",
        }
    except Exception as e:
        logger.error(f"Unexpected error for {team_upper}: {e}")
        return team_abbrev, {
            "status": "error",
            "message": f"Unexpected error: {e!s}",
        }


@tool(args_schema=GetTeamScheduleInput)
def get_team_schedule(team_abbrevs: list[str]) -> str:
    """
    Get the number of games each NHL team has for the remainder of this week and next week.

    This is useful for fantasy hockey decisions - players on teams with more games
    have more opportunities to accumulate points. This tool fetches the schedule
    from the official NHL API.

    Args:
        team_abbrevs: List of NHL team abbreviations (e.g., ['TOR', 'BOS', 'EDM'])

    Returns:
        JSON string containing game counts and schedule details for each team
    """
    # Calculate date range: today through end of next week (Sunday)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Find the end of next week (next Sunday after this week's Sunday)
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7  # If today is Sunday, go to next Sunday
    this_sunday = today + timedelta(days=days_until_sunday)
    next_sunday = this_sunday + timedelta(days=7)

    results = {}

    # Fetch all team schedules concurrently
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
