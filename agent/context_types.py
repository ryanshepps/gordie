from typing import Literal, Required

from typing_extensions import TypedDict

ContextStatus = Literal[
    "validated",
    "first_time_user",
    "no_oauth",
    "no_teams_in_db",
    "no_teams_available",
    "team_selection_needed",
    "team_ambiguous",
    "auto_onboarded",
    "billing_blocked",
    "error",
]

Sport = Literal["nhl", "mlb", "nfl", "nba"]


class ContextResult(TypedDict, total=False):
    context_status: Required[ContextStatus]
    sport: Sport
    sport_inferred_at: str
    league_id: str
    team_id: str
    oauth_url: str
    available_teams: list[dict[str, str]]
    context_error: str
