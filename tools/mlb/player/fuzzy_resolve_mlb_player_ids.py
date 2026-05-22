from __future__ import annotations

import json
from dataclasses import dataclass

import requests
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


@dataclass(frozen=True, slots=True)
class MlbPlayerMatch:
    player_id: int
    full_name: str
    team_abbrev: str
    position: str
    active: bool


class FuzzyResolveMlbInput(BaseModel):
    player_names: list[str] = Field(
        description="List of MLB player names to resolve (e.g., ['Shohei Ohtani', 'Aaron Judge'])"
    )


def _search_mlb_api(player_name: str) -> list[MlbPlayerMatch]:
    url = f"{MLB_API_BASE}/people/search?names={player_name}&sportId=1"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to search MLB API for '{player_name}': {e}")
        return []

    matches: list[MlbPlayerMatch] = []
    for person in data.get("people", []):
        player_id = person.get("id")
        full_name = person.get("fullName", "")
        team_abbrev = person.get("currentTeam", {}).get("abbreviation", "")
        position = person.get("primaryPosition", {}).get("abbreviation", "")
        active = person.get("active", False)

        if player_id and full_name:
            matches.append(
                MlbPlayerMatch(
                    player_id=player_id,
                    full_name=full_name,
                    team_abbrev=team_abbrev,
                    position=position,
                    active=active,
                )
            )

    return matches


def fuzzy_resolve_mlb_player_ids(player_names: list[str]) -> str:
    """
    Resolve MLB player names to their official MLB API player IDs.

    Searches the MLB Stats API for each player name and returns matching
    player records with IDs, team, and position info.

    Args:
        player_names: List of player names to search for

    Returns:
        JSON string with search results per player name
    """
    results: dict[str, list[dict[str, str | int | bool]] | dict[str, str]] = {}

    for name in player_names:
        matches = _search_mlb_api(name)

        if not matches:
            results[name] = {
                "status": "not_found",
                "message": f"No MLB players found matching '{name}'",
            }
            continue

        if len(matches) == 1:
            match = matches[0]
            results[name] = [
                {
                    "player_id": match.player_id,
                    "full_name": match.full_name,
                    "team": match.team_abbrev,
                    "position": match.position,
                    "active": match.active,
                    "status": "exact_match",
                }
            ]
        else:
            results[name] = [
                {
                    "player_id": m.player_id,
                    "full_name": m.full_name,
                    "team": m.team_abbrev,
                    "position": m.position,
                    "active": m.active,
                    "status": "multiple_matches",
                }
                for m in matches[:5]
            ]

    return json.dumps(results, indent=2)
