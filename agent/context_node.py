from datetime import UTC, datetime
from uuid import UUID

from agent.agent_state import AgentState
from agent.context_resolvers import (
    auto_onboard_team,
    check_oauth_status,
    fetch_supported_teams,
    is_first_time_user,
    resolve_team_context,
)
from agent.context_types import ContextResult, Sport
from agent.sport_inference import infer_sport
from data.models import Medium
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.logger import get_logger
from tools.oauth.generate_oauth_link import generate_oauth_link

logger = get_logger(__name__)


def _fetch_onboarded_teams(user_id: str) -> list[dict[str, str]]:
    repo = YahooUserTeamRepository()
    try:
        return repo.get_user_teams_with_league_info_by_user_id(UUID(user_id))
    finally:
        repo.close()


VALID_SPORTS: set[Sport] = {"nhl", "mlb", "nfl", "nba"}


def _extract_last_human_message(state: AgentState) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("type") == "human":
            return str(msg.get("content", ""))
    return ""


def _infer_sport(user_teams: list[dict[str, str]], league_id: str) -> Sport:
    for team in user_teams:
        if team.get("league_id") == league_id:
            sport = team.get("sport", "nhl")
            if sport in VALID_SPORTS:
                return sport  # type: ignore[return-value]
            logger.warning(f"Unknown sport '{sport}' for league {league_id}, defaulting to nhl")
            return "nhl"
    logger.warning(f"No team found for league_id={league_id}, defaulting to nhl")
    return "nhl"


def _handle_no_teams(user_id: str) -> ContextResult:
    try:
        teams = fetch_supported_teams(user_id)
    except Exception as e:
        logger.error(f"Error fetching available teams for user_id={user_id}: {e}")
        return ContextResult(
            context_status="error",
            context_error=f"Failed to fetch Yahoo Fantasy teams: {e}",
        )

    if not teams:
        return ContextResult(context_status="no_teams_available")

    active_teams = [t for t in teams if t.get("is_active", False)]
    if len(active_teams) == 1:
        team = auto_onboard_team(user_id, active_teams[0])
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

    user_id = state.get("user_id", "")
    if not user_id:
        return ContextResult(context_status="error", context_error="No user ID found")

    has_oauth = check_oauth_status(user_id)

    if not has_oauth:
        from agent.memory_store import get_memory_store

        first_time = is_first_time_user(user_id, get_memory_store())
        thread_id = state.get("thread_id", "")
        channel = state.get("channel", Medium.EMAIL)
        medium = channel if isinstance(channel, Medium) else Medium(channel)
        external_id = state.get("external_id", "")
        oauth_url = generate_oauth_link.invoke(
            {"external_id": external_id, "thread_id": thread_id, "channel": medium}
        )
        status = "first_time_user" if first_time else "no_oauth"
        return ContextResult(context_status=status, oauth_url=oauth_url)

    onboarded_teams = _fetch_onboarded_teams(user_id)
    if not onboarded_teams:
        return _handle_no_teams(user_id)

    league_id, team_id = resolve_team_context(state, onboarded_teams)
    if league_id and team_id:
        sport = _infer_sport(onboarded_teams, league_id)
        return ContextResult(
            context_status="validated",
            league_id=league_id,
            team_id=team_id,
            sport=sport,
            sport_inferred_at=datetime.now(UTC).isoformat(),
        )

    message_text = _extract_last_human_message(state)
    inferred_sport = infer_sport(
        message_text=message_text,
        user_teams=onboarded_teams,
        current_sport=state.get("sport"),
        sport_inferred_at=state.get("sport_inferred_at"),
    )

    if inferred_sport:
        sport_teams = [t for t in onboarded_teams if t.get("sport") == inferred_sport]
        if len(sport_teams) == 1:
            team = sport_teams[0]
            return ContextResult(
                context_status="validated",
                league_id=team["league_id"],
                team_id=team["team_id"],
                sport=inferred_sport,
                sport_inferred_at=datetime.now(UTC).isoformat(),
            )

    return ContextResult(
        context_status="team_ambiguous",
        available_teams=onboarded_teams,
    )
