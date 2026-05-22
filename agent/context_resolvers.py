import ast
import logging

from langgraph.store.base import BaseStore

from agent.agent_state import AgentState
from tools.yahoo.get_user_leagues import get_user_leagues
from tools.yahoo.onboard_user_team import onboard_user_team

logger = logging.getLogger(__name__)


def sanitize_namespace_label(label: str) -> str:
    return label.replace(".", "_dot_")


def is_first_time_user(user_id: str, memory_store: BaseStore) -> bool:
    try:
        namespace = ("memories", user_id)
        results = memory_store.search(namespace, query="", limit=1)

        if results and len(results) > 0:
            return False

        logger.info(f"First time user: {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error checking first-time user: {e}")
        return False


def check_oauth_status(user_id: str) -> bool:
    from data.yahoo_token_repository import load_tokens_from_db_by_user_id

    user_tokens = load_tokens_from_db_by_user_id(user_id)
    return user_tokens is not None


def resolve_team_context(
    state: AgentState, user_teams: list[dict[str, str]]
) -> tuple[str | None, str | None]:
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        team_context = None

        if hasattr(last_message, "team_context"):
            team_context = last_message.team_context
        elif isinstance(last_message, dict):
            team_context = last_message.get("team_context")

        if team_context and ":" in team_context:
            parts = team_context.split(":")
            if len(parts) >= 4:
                return parts[2], parts[3]

    if state.get("league_id") and state.get("team_id"):
        return state.get("league_id"), state.get("team_id")

    if len(user_teams) == 1:
        team = user_teams[0]
        return team["league_id"], team["team_id"]

    return None, None


SUPPORTED_SPORTS: set[str] = {"nhl", "mlb", "nfl", "nba"}


def fetch_supported_teams(user_id: str) -> list[dict[str, str]]:
    available_teams_str = get_user_leagues.invoke({"user_id": user_id})

    if available_teams_str.startswith("Error"):
        raise RuntimeError(f"Failed to fetch user leagues: {available_teams_str}")

    try:
        available_teams = ast.literal_eval(available_teams_str)
    except (ValueError, SyntaxError) as e:
        logger.error(f"Failed to parse teams data: {e}. Raw data: {available_teams_str[:200]}")
        raise RuntimeError(f"Invalid teams data format: {e}") from e

    supported_teams: list[dict[str, str]] = [
        team for team in available_teams if team.get("sport") in SUPPORTED_SPORTS
    ]

    return supported_teams


def format_teams_for_display(teams: list[dict[str, str]]) -> str:
    teams_list = []
    for team in teams:
        active_status = "Active" if team.get("is_active", False) else "Off-season"
        sport_label = team.get("sport", "unknown").upper()
        team_str = (
            f"  - [{sport_label}] Team: {team['team_name']}\n"
            f"    Season: {team['season']} ({active_status})\n"
            f"    game_key={team['game_key']}, league_id={team['league_id']}, team_id={team['team_id']}"
        )
        teams_list.append(team_str)

    return "\n\n".join(teams_list)


def auto_onboard_team(user_id: str, team: dict[str, str]) -> dict[str, str]:
    logger.info(f"Auto-onboarding single active team '{team['team_name']}' for user_id={user_id}")

    onboard_user_team.invoke(
        {
            "game_key": team["game_key"],
            "game_code": team.get("sport", "nhl"),
            "league_id": int(team["league_id"]),
            "team_name": team["team_name"],
            "team_id": int(team["team_id"]),
            "state": {"user_id": user_id},
        }
    )

    return team
