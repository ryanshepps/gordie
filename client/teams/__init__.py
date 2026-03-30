from __future__ import annotations

from collections.abc import Callable

from agent.context_types import Sport
from client.teams.mlb_teams import MLB_TEAMS, mlb_team_abbr
from client.teams.nhl_teams import NHL_TEAMS, nhl_team_abbr

_TEAM_ABBR_FNS: dict[Sport, Callable[[str], str]] = {
    "nhl": nhl_team_abbr,
    "mlb": mlb_team_abbr,
}

_TEAMS: dict[Sport, dict[str, str]] = {
    "nhl": NHL_TEAMS,
    "mlb": MLB_TEAMS,
}


def get_team_abbr(sport: Sport, name: str) -> str:
    fn = _TEAM_ABBR_FNS.get(sport)
    if fn is None:
        return name.upper()[:3]
    return fn(name)


def get_teams(sport: Sport) -> dict[str, str]:
    return _TEAMS.get(sport, {})
