from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from agent.news.news_digest import MatchupAlert
from module.logger import get_logger

logger = get_logger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

WEAK_OPPONENT_ERA_THRESHOLD = 4.50


def fetch_mlb_matchups() -> list[MatchupAlert]:
    today = datetime.now().strftime("%Y-%m-%d")
    return fetch_mlb_matchups_for_date(today)


def fetch_mlb_matchups_for_date(date_str: str) -> list[MatchupAlert]:
    try:
        schedule = _fetch_schedule(date_str)
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch MLB schedule for {date_str}: {e}")
        return []

    if not schedule:
        logger.info(f"No MLB games scheduled for {date_str}")
        return []

    team_era_cache: dict[str, float] = {}
    matchups: list[MatchupAlert] = []

    for game in schedule:
        try:
            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})

            home_team = home.get("team", {})
            away_team = away.get("team", {})

            home_abbr = home_team.get("abbreviation", "")
            away_abbr = away_team.get("abbreviation", "")
            home_id = home_team.get("id")
            away_id = away_team.get("id")

            if not home_abbr or not away_abbr:
                continue

            home_era = team_era_cache.get(home_abbr)
            if home_era is None:
                home_era = _get_team_era(home_id)
                team_era_cache[home_abbr] = home_era

            away_era = team_era_cache.get(away_abbr)
            if away_era is None:
                away_era = _get_team_era(away_id)
                team_era_cache[away_abbr] = away_era

            if home_era >= WEAK_OPPONENT_ERA_THRESHOLD:
                away_roster = _get_team_active_batters(away_id)
                for player_name in away_roster:
                    matchups.append(
                        MatchupAlert(
                            player_name=player_name,
                            opponent=home_abbr,
                            opponent_weakness_metric=home_era,
                            metric_label="ERA",
                        )
                    )

            if away_era >= WEAK_OPPONENT_ERA_THRESHOLD:
                home_roster = _get_team_active_batters(home_id)
                for player_name in home_roster:
                    matchups.append(
                        MatchupAlert(
                            player_name=player_name,
                            opponent=away_abbr,
                            opponent_weakness_metric=away_era,
                            metric_label="ERA",
                        )
                    )

        except Exception as e:
            logger.warning(f"Error processing MLB game: {e}")
            continue

    logger.info(f"Generated {len(matchups)} MLB matchup alerts for {date_str}")
    return matchups


def _fetch_schedule(date_str: str) -> list[dict[str, Any]]:
    url = f"{MLB_API_BASE}/schedule?date={date_str}&sportId=1"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data: dict[str, Any] = response.json()

    games: list[dict[str, Any]] = []
    for date_entry in data.get("dates", []):
        games.extend(date_entry.get("games", []))
    return games


def _get_team_era(team_id: int | None) -> float:
    if team_id is None:
        return 4.20

    year = datetime.now().year
    url = f"{MLB_API_BASE}/teams/{team_id}/stats?stats=season&season={year}&group=pitching"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        for stat_group in data.get("stats", []):
            for split in stat_group.get("splits", []):
                era_str = split.get("stat", {}).get("era", "")
                if era_str:
                    return float(era_str)
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"Error fetching ERA for team {team_id}: {e}")

    return 4.20


def _get_team_active_batters(team_id: int | None) -> list[str]:
    if team_id is None:
        return []

    url = f"{MLB_API_BASE}/teams/{team_id}/roster?rosterType=active"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        batters: list[str] = []
        for entry in data.get("roster", []):
            position = entry.get("position", {}).get("abbreviation", "")
            if position in ("P", "TWP"):
                continue
            full_name = entry.get("person", {}).get("fullName", "")
            if full_name:
                batters.append(full_name)
        return batters

    except requests.RequestException as e:
        logger.warning(f"Error fetching roster for team {team_id}: {e}")
        return []
