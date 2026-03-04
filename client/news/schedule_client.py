from __future__ import annotations

from datetime import datetime

from nhlpy import NHLClient

from module.logger import get_logger

logger = get_logger(__name__)


def fetch_teams_playing_today() -> set[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    return fetch_teams_playing_on_date(today)


def fetch_teams_playing_on_date(date_str: str) -> set[str]:
    client = NHLClient()

    try:
        schedule = client.schedule.daily_schedule(date_str)
    except Exception as e:
        logger.warning(f"Failed to fetch NHL schedule for {date_str}: {e}")
        return set()

    if not schedule or "games" not in schedule:
        return set()

    teams: set[str] = set()
    for game in schedule["games"]:
        home_abbrev = game.get("homeTeam", {}).get("abbrev", "")
        away_abbrev = game.get("awayTeam", {}).get("abbrev", "")
        if home_abbrev:
            teams.add(home_abbrev)
        if away_abbrev:
            teams.add(away_abbrev)

    logger.info(f"Found {len(teams)} teams playing on {date_str}")
    return teams
