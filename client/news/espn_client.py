from __future__ import annotations

from typing import Any

import requests

from agent.context_types import Sport
from agent.news.news_digest import InjuryAlert
from client.teams import get_team_abbr
from module.logger import get_logger

logger = get_logger(__name__)

ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

ESPN_SPORT_PATHS: dict[Sport, str] = {
    "nhl": "hockey/nhl",
    "mlb": "baseball/mlb",
    "nfl": "football/nfl",
    "nba": "basketball/nba",
}

STATUS_MAP: dict[str, str] = {
    "out": "OUT",
    "day-to-day": "DTD",
    "injured reserve": "IR",
    "questionable": "DTD",
    "doubtful": "OUT",
    "suspension": "OUT",
}


def fetch_injuries(sport: Sport = "nhl") -> list[InjuryAlert]:
    sport_path = ESPN_SPORT_PATHS.get(sport)
    if sport_path is None:
        logger.warning(f"No ESPN injuries endpoint for sport: {sport}")
        return []

    url = f"{ESPN_API_BASE}/{sport_path}/injuries"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch ESPN injuries API for {sport}: {e}")
        return []
    except ValueError as e:
        logger.warning(f"Failed to parse ESPN injuries JSON for {sport}: {e}")
        return []

    return _parse_injuries_response(data, sport)


def _parse_injuries_response(data: dict[str, Any], sport: Sport) -> list[InjuryAlert]:
    alerts: list[InjuryAlert] = []

    team_entries = data.get("injuries", [])

    for team_entry in team_entries:
        team_name = team_entry.get("displayName", "")
        team_abbr = get_team_abbr(sport, team_name)

        team_injuries = team_entry.get("injuries", [])
        for injury in team_injuries:
            alert = _extract_injury_alert(injury, team_abbr)
            if alert:
                alerts.append(alert)

    logger.info(f"Parsed {len(alerts)} injury alerts from ESPN API for {sport}")
    return alerts


def _extract_injury_alert(injury: dict[str, Any], team_abbr: str) -> InjuryAlert | None:
    athlete = injury.get("athlete", {})
    player_name = athlete.get("displayName", "")

    if not player_name:
        return None

    raw_status = injury.get("status", "").lower()
    status = STATUS_MAP.get(raw_status, "OUT")

    description = injury.get("longComment", "") or injury.get("shortComment", "")

    return InjuryAlert(
        player_name=player_name,
        team=team_abbr,
        status=status,
        description=description,
    )
