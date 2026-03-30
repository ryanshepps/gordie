"""Tool to resolve player names to NHL API player IDs."""

import json
from dataclasses import dataclass
from typing import Literal

import requests
from pydantic import BaseModel, Field

from client.moneypuck_cli import search_player as moneypuck_search_cli
from module.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PlayerMatch:
    """A matched player from local database or NHL API."""

    player_id: int
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    games_in_db: int | None = None
    team_abbrev: str | None = None
    position: str | None = None
    active: bool | None = None


class FuzzyResolveNHLApiPlayerIdsInput(BaseModel):
    """Input schema for fuzzy_resolve_nhl_api_player_ids tool."""

    player_names: list[str] = Field(
        description="List of player names to resolve (e.g., ['McDavid', 'Draisaitl'])"
    )


class PlayerMatchDict(BaseModel):
    """A player match with all optional fields included."""

    player_id: int
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    games_in_db: int | None = None
    team_abbrev: str | None = None
    position: str | None = None
    active: bool | None = None


class SingleMatchResult(BaseModel):
    """Result when exactly one player match is found."""

    status: Literal["success"]
    source: str
    player_id: int
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    games_in_db: int | None = None
    team_abbrev: str | None = None
    position: str | None = None
    active: bool | None = None
    message: str | None = None


class MultipleMatchResult(BaseModel):
    """Result when multiple player matches are found."""

    status: Literal["multiple_matches"]
    source: str
    matches: list[PlayerMatchDict]
    message: str


BuildResultOutput = SingleMatchResult | MultipleMatchResult


def _search_moneypuck(player_name: str) -> list[PlayerMatch]:
    """Search MoneyPuck data for players matching the name via CLI."""
    try:
        results = moneypuck_search_cli(player_name)
        if not results:
            return []

        return [
            PlayerMatch(
                player_id=int(r.get("player_id", r.get("playerId", 0))),
                full_name=str(r.get("name", "")),
                team_abbrev=str(r["team"]) if r.get("team") else None,
                position=str(r["position"]) if r.get("position") else None,
                games_in_db=int(r["games_played"]) if r.get("games_played") else None,
            )
            for r in results[:5]
        ]
    except Exception as e:
        logger.error(f"MoneyPuck search error for '{player_name}': {e}")
        return []


def _search_nhl_api(player_name: str) -> list[PlayerMatch] | None:
    """Search NHL API for players matching the name. Returns None on error."""
    try:
        url = (
            f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=5&q={player_name}"
        )
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        results = response.json()
        return [
            PlayerMatch(
                player_id=int(p.get("playerId", 0)),
                full_name=p.get("name", ""),
                team_abbrev=p.get("teamAbbrev"),
                position=p.get("positionCode"),
                active=p.get("active", False),
            )
            for p in results
        ]
    except requests.RequestException as e:
        logger.error(f"NHL API error for '{player_name}': {e}")
        return None


def _build_result(matches: list[PlayerMatch], source: str) -> BuildResultOutput:
    """Build result dict for single or multiple matches."""
    if len(matches) == 1:
        match = matches[0]
        return SingleMatchResult(
            status="success",
            source=source,
            player_id=match.player_id,
            full_name=match.full_name,
            first_name=match.first_name,
            last_name=match.last_name,
            games_in_db=match.games_in_db,
            team_abbrev=match.team_abbrev,
            position=match.position,
            active=match.active,
            message=(
                "Player found via NHL API. Stats may not be in local database yet."
                if source == "nhl_api"
                else None
            ),
        )

    # Multiple matches
    return MultipleMatchResult(
        status="multiple_matches",
        source=source,
        matches=[
            PlayerMatchDict(
                player_id=m.player_id,
                full_name=m.full_name,
                first_name=m.first_name,
                last_name=m.last_name,
                games_in_db=m.games_in_db,
                team_abbrev=m.team_abbrev,
                position=m.position,
                active=m.active,
            )
            for m in matches
        ],
        message=f"Found {len(matches)} possible matches. Please be more specific.",
    )


def fuzzy_resolve_nhl_api_player_ids(player_names: list[str]) -> str:
    """
    Resolve player names to NHL API player IDs using MoneyPuck and NHL search API.

    This tool uses a two-tier approach:
    1. First searches MoneyPuck data (current season stats) with fuzzy matching
    2. Falls back to NHL search API if not found in MoneyPuck

    Args:
        player_names: List of player names to search for (e.g., ['McDavid', 'Draisaitl'])

    Returns:
        JSON string with resolved player information (player_id, full_name, match details)
    """
    results = {}

    for player_name in player_names:
        try:
            logger.info(f"Searching for player: {player_name}")

            # Try MoneyPuck first (has current season data)
            moneypuck_matches = _search_moneypuck(player_name)
            if moneypuck_matches:
                match_count = len(moneypuck_matches)
                logger.info(f"Found {match_count} MoneyPuck match(es) for '{player_name}'")
                result = _build_result(moneypuck_matches, "moneypuck")
                results[player_name] = result.model_dump(exclude_none=True)
                continue

            # Fall back to NHL API (includes inactive players, prospects, etc.)
            logger.info(f"No MoneyPuck match for '{player_name}', trying NHL API")
            api_matches = _search_nhl_api(player_name)

            if api_matches is None:
                results[player_name] = {"status": "error", "message": "Could not search NHL API"}
                continue

            if not api_matches:
                logger.warning(f"No matches found for '{player_name}'")
                results[player_name] = {
                    "status": "not_found",
                    "message": f"No player found matching '{player_name}' in MoneyPuck or NHL API",
                }
                continue

            logger.info(f"Found {len(api_matches)} NHL API match(es) for '{player_name}'")
            result = _build_result(api_matches, "nhl_api")
            results[player_name] = result.model_dump(exclude_none=True)

        except Exception as e:
            logger.error(f"Error resolving '{player_name}': {e}")
            results[player_name] = {"status": "error", "error": str(e)}

    return json.dumps(results, indent=2)
