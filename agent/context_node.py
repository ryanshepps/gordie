import logging

from agent.agent_state import AgentState
from agent.context_resolvers import (
    auto_onboard_team,
    check_oauth_status,
    fetch_supported_teams,
    is_first_time_user,
    resolve_team_context,
)
from agent.context_types import ContextResult, Sport
from data.yahoo_user_team_repository import YahooUserTeamRepository
from tools.oauth.generate_oauth_link import generate_oauth_link

logger = logging.getLogger(__name__)


def _fetch_onboarded_teams(user_email: str) -> list[dict[str, str]]:
    repo = YahooUserTeamRepository()
    try:
        return repo.get_user_teams_with_league_info(user_email)
    finally:
        repo.close()


def _infer_sport(user_teams: list[dict[str, str]], league_id: str) -> Sport:
    for team in user_teams:
        if team.get("league_id") == league_id:
            return "nhl"
    return "nhl"


def _handle_no_teams(user_email: str) -> ContextResult:
    try:
        teams = fetch_supported_teams(user_email)
    except Exception as e:
        logger.error(f"Error fetching available teams for {user_email}: {e}")
        return ContextResult(
            context_status="error",
            context_error=f"Failed to fetch Yahoo Fantasy teams: {e}",
        )

    if not teams:
        return ContextResult(context_status="no_teams_available")

    active_teams = [t for t in teams if t.get("is_active", False)]
    if len(active_teams) == 1:
        team = auto_onboard_team(user_email, active_teams[0])
        return ContextResult(
            context_status="auto_onboarded",
            league_id=team["league_id"],
            team_id=team["team_id"],
            sport=_infer_sport([team], team["league_id"]),
        )

    return ContextResult(
        context_status="team_selection_needed",
        available_teams=teams,
    )


def context_node(state: AgentState) -> ContextResult:
    if state.get("billing_context"):
        return ContextResult(context_status="billing_blocked")

    user_email = state.get("user_email", "")
    if not user_email:
        return ContextResult(context_status="error", context_error="No user email found")

    has_oauth = check_oauth_status(user_email)

    if not has_oauth:
        from agent.memory_store import get_memory_store

        first_time = is_first_time_user(user_email, get_memory_store())
        thread_id = state.get("thread_id", "")
        oauth_url = generate_oauth_link.invoke(
            {"user_email": user_email, "thread_id": thread_id, "channel": "email"}
        )
        status = "first_time_user" if first_time else "no_oauth"
        return ContextResult(context_status=status, oauth_url=oauth_url)

    onboarded_teams = _fetch_onboarded_teams(user_email)
    if not onboarded_teams:
        return _handle_no_teams(user_email)

    league_id, team_id = resolve_team_context(state, onboarded_teams)
    if not league_id or not team_id:
        return ContextResult(
            context_status="team_ambiguous",
            available_teams=onboarded_teams,
        )

    sport = _infer_sport(onboarded_teams, league_id)
    return ContextResult(
        context_status="validated",
        league_id=league_id,
        team_id=team_id,
        sport=sport,
    )
