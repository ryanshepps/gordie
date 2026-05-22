from __future__ import annotations

from datetime import datetime

import requests

from module.logger import get_logger

logger = get_logger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


def fetch_mlb_teams_playing_today() -> set[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    return fetch_mlb_teams_playing_on_date(today)


def fetch_mlb_teams_playing_on_date(date_str: str) -> set[str]:
    url = f"{MLB_API_BASE}/schedule?date={date_str}&sportId=1"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch MLB schedule for {date_str}: {e}")
        return set()

    teams: set[str] = set()
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            home_abbr = (
                game.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", "")
            )
            away_abbr = (
                game.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", "")
            )
            if home_abbr:
                teams.add(home_abbr)
            if away_abbr:
                teams.add(away_abbr)

    logger.info(f"Found {len(teams)} MLB teams playing on {date_str}")
    return teams
