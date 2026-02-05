"""ESPN client for fetching NHL injury data.

Fetches injury data from ESPN's public API and parses them
into structured InjuryAlert objects.
"""

from __future__ import annotations

from typing import Any

import requests

from agent.news.news_digest import InjuryAlert
from module.logger import get_logger

logger = get_logger(__name__)

# ESPN NHL Injuries API endpoint
ESPN_INJURIES_API_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"

# Status normalization map
STATUS_MAP = {
    "out": "OUT",
    "day-to-day": "DTD",
    "injured reserve": "IR",
    "questionable": "DTD",
    "doubtful": "OUT",
    "suspension": "OUT",
}


def fetch_injuries() -> list[InjuryAlert]:
    """Fetch injury alerts from ESPN NHL injuries API.

    Returns:
        List of InjuryAlert objects from the API

    Note:
        Returns empty list on fetch failure rather than raising exception
        to allow the news digest to proceed with partial data.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    try:
        response = requests.get(ESPN_INJURIES_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch ESPN injuries API: {e}")
        return []
    except ValueError as e:
        logger.warning(f"Failed to parse ESPN injuries JSON: {e}")
        return []

    return _parse_injuries_response(data)


def _parse_injuries_response(data: dict[str, Any]) -> list[InjuryAlert]:
    """Parse ESPN injuries API response into InjuryAlert objects.

    Args:
        data: JSON response from ESPN injuries API

    Returns:
        List of InjuryAlert objects
    """
    alerts: list[InjuryAlert] = []

    # Response structure: { "injuries": [ { "displayName": "Team", "injuries": [...] } ] }
    team_entries = data.get("injuries", [])

    for team_entry in team_entries:
        team_name = team_entry.get("displayName", "NHL")
        # Extract team abbreviation from full name (e.g., "Anaheim Ducks" -> "ANA")
        team_abbr = _get_team_abbr(team_name)

        team_injuries = team_entry.get("injuries", [])
        for injury in team_injuries:
            alert = _extract_injury_alert(injury, team_abbr)
            if alert:
                alerts.append(alert)

    logger.info(f"Parsed {len(alerts)} injury alerts from ESPN API")
    return alerts


def _extract_injury_alert(injury: dict[str, Any], team_abbr: str) -> InjuryAlert | None:
    """Extract injury alert from API injury entry.

    Args:
        injury: Single injury entry from API
        team_abbr: Team abbreviation

    Returns:
        InjuryAlert if valid, None otherwise
    """
    athlete = injury.get("athlete", {})
    player_name = athlete.get("displayName", "")

    if not player_name:
        return None

    # Get status and normalize it
    raw_status = injury.get("status", "").lower()
    status = STATUS_MAP.get(raw_status, "OUT")

    # Get description from longComment or shortComment
    description = injury.get("longComment", "") or injury.get("shortComment", "")

    return InjuryAlert(
        player_name=player_name,
        team=team_abbr,
        status=status,
        description=description,
    )


def _get_team_abbr(team_name: str) -> str:
    """Convert team full name to abbreviation.

    Args:
        team_name: Full team name (e.g., "Anaheim Ducks")

    Returns:
        Team abbreviation (e.g., "ANA")
    """
    team_map = {
        "Anaheim Ducks": "ANA",
        "Arizona Coyotes": "ARI",
        "Utah Hockey Club": "UTA",
        "Boston Bruins": "BOS",
        "Buffalo Sabres": "BUF",
        "Calgary Flames": "CGY",
        "Carolina Hurricanes": "CAR",
        "Chicago Blackhawks": "CHI",
        "Colorado Avalanche": "COL",
        "Columbus Blue Jackets": "CBJ",
        "Dallas Stars": "DAL",
        "Detroit Red Wings": "DET",
        "Edmonton Oilers": "EDM",
        "Florida Panthers": "FLA",
        "Los Angeles Kings": "LAK",
        "Minnesota Wild": "MIN",
        "Montreal Canadiens": "MTL",
        "Nashville Predators": "NSH",
        "New Jersey Devils": "NJD",
        "New York Islanders": "NYI",
        "New York Rangers": "NYR",
        "Ottawa Senators": "OTT",
        "Philadelphia Flyers": "PHI",
        "Pittsburgh Penguins": "PIT",
        "San Jose Sharks": "SJS",
        "Seattle Kraken": "SEA",
        "St. Louis Blues": "STL",
        "Tampa Bay Lightning": "TBL",
        "Toronto Maple Leafs": "TOR",
        "Vancouver Canucks": "VAN",
        "Vegas Golden Knights": "VGK",
        "Washington Capitals": "WSH",
        "Winnipeg Jets": "WPG",
    }
    return team_map.get(team_name, "NHL")
