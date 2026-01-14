"""
Context Validation Pipeline
===========================

This module validates user context in 5 steps:

1. Email validation - Ensure we have a user email
2. Authentication check - First-time user or OAuth status
3. Team availability - Check if user has onboarded teams
4. Team resolution - Resolve which team the user is asking about
5. Final validation - All checks passed

Each step returns early with instructions for Gordie if validation fails.
Only when all steps pass does the user get full access.
"""

import ast
import logging
from dataclasses import dataclass

from langgraph.store.base import BaseStore

from agent.agent_state import AgentState
from data.yahoo_user_team_repository import YahooUserTeamRepository
from tools.oauth.generate_oauth_link import generate_oauth_link
from tools.yahoo.get_user_leagues import get_user_leagues

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of context validation."""

    system_message: str
    league_id: str | None = None
    team_id: str | None = None


def _sanitize_namespace_label(label: str) -> str:
    """LangGraph store namespace uses "." for hierarchical paths internally."""
    return label.replace(".", "_dot_")


def _is_first_time_user(user_email: str, memory_store: BaseStore) -> bool:
    """
    Check if this user has ever messaged Gordie before.

    Checks the memory store for any past conversations with this user.
    """
    try:
        sanitized_email = _sanitize_namespace_label(user_email)
        namespace = ("memories", sanitized_email)
        results = memory_store.search(namespace, query="", limit=1)

        if results and len(results) > 0:
            return False

        logger.info(f"First time user: {user_email}")
        return True

    except Exception as e:
        logger.error(f"Error checking first-time user: {e}")
        return False


def _resolve_team_context(
    state: AgentState, user_teams: list[dict[str, str]]
) -> tuple[str | None, str | None]:
    """
    Try to resolve team context from state or message.

    Returns: (league_id, team_id) or (None, None) if can't resolve
    """
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


def _extract_user_info(state: AgentState) -> tuple[str, str]:
    """Extract user email and thread ID from state."""
    user_email = state.get("user_email", "")
    thread_id = state.get("thread_id", "")
    return user_email, thread_id


def _handle_missing_email() -> ValidationResult:
    """Handle case where user email is missing from state."""
    return ValidationResult(
        system_message="Error: No user email found. Tell the user there was an error and to try again.",
    )


def _check_oauth_status(user_email: str) -> bool:
    """Check if user has valid OAuth tokens."""
    from data.yahoo_token_repository import load_tokens_from_db

    user_tokens = load_tokens_from_db(user_email)
    return user_tokens is not None


def _handle_first_time_or_no_oauth(
    user_email: str, thread_id: str, is_first_time: bool, has_oauth: bool
) -> ValidationResult:
    """Handle first-time users or users without OAuth tokens."""
    oauth_url = generate_oauth_link.invoke({"user_email": user_email, "thread_id": thread_id})

    if is_first_time:
        system_message = f"""FIRST TIME USER DETECTED

This is the very first message from this user.

Your response MUST:
1. Introduce yourself as Gordie
2. Explain your capabilities (roster advice, trade analysis, player comparisons, waiver wire help)
3. Ask them to connect their Yahoo Fantasy Hockey team using this OAuth link: {oauth_url}
4. Be friendly and welcoming

Do NOT proceed with any fantasy-specific requests until they onboard."""
    else:
        system_message = f"""NO OAUTH TOKENS

The user does not have valid Yahoo authentication.

Your response MUST:
1. Tell them they need to connect their Yahoo Fantasy Hockey account
2. Provide this OAuth link: {oauth_url}
3. Explain that you cannot help with fantasy requests until they authenticate

Do NOT proceed with their request."""

    return ValidationResult(system_message=system_message)


def _fetch_hockey_teams(user_email: str) -> list[dict[str, str]]:
    """
    Fetch user's hockey teams from Yahoo.

    Returns list of hockey teams (sport='nhl').
    Raises exception if API call fails.
    """
    available_teams_str = get_user_leagues.invoke({"user_email": user_email})
    available_teams = ast.literal_eval(available_teams_str)

    hockey_teams = [team for team in available_teams if team.get("sport") == "nhl"]

    return hockey_teams


def _format_teams_for_display(teams: list[dict[str, str]]) -> str:
    """Format list of teams for display to user."""
    teams_list = []
    for team in teams:
        active_status = "Active" if team.get("is_active", False) else "Off-season"
        team_str = (
            f"  - Team: {team['team_name']}\n"
            f"    Season: {team['season']} ({active_status})\n"
            f"    game_key={team['game_key']}, league_id={team['league_id']}, team_id={team['team_id']}"
        )
        teams_list.append(team_str)

    return "\n\n".join(teams_list)


def _build_team_selection_message(formatted_teams: str, user_email: str) -> str:
    """Build system message prompting Gordie to help user select a team."""
    return f"""SELECT TEAM TO ONBOARD

The user has authenticated with Yahoo. Here are their available Fantasy Hockey teams:

{formatted_teams}

Your response MUST:
1. Ask them which team they want to track with Gordie
2. Once they indicate their choice, call the 'onboard_user_team' tool with:
   - user_email: {user_email}
   - game_key: (from the team they selected)
   - league_id: (from the team they selected)
   - team_name: (from the team they selected)
   - team_id: (from the team they selected)
3. After successfully onboarding, proceed with their original request if they had one

Do NOT ask them for technical IDs - just ask which team/league name, then YOU extract the IDs from the list above."""


def _handle_no_teams_in_db(user_email: str) -> ValidationResult:
    """
    Handle case where user is authenticated but has no teams in database.

    Fetches available teams from Yahoo and prompts user to select one.
    """
    logger.info(
        f"User {user_email} is authenticated but has no teams. Fetching available teams from Yahoo."
    )

    try:
        hockey_teams = _fetch_hockey_teams(user_email)

        if not hockey_teams:
            system_message = """NO HOCKEY TEAMS AVAILABLE

The user has authenticated with Yahoo but has no Fantasy Hockey teams.

Your response MUST:
1. Explain that they don't have any Yahoo Fantasy Hockey teams
2. Tell them to create a hockey team on Yahoo Fantasy first
3. Once they have a hockey team, they can come back and you'll help them onboard

Do NOT proceed with their request."""
            return ValidationResult(system_message=system_message)

        formatted_teams = _format_teams_for_display(hockey_teams)
        system_message = _build_team_selection_message(formatted_teams, user_email)

        return ValidationResult(system_message=system_message)

    except Exception as e:
        logger.error(f"Error fetching available teams for {user_email}: {e}")
        system_message = f"""ERROR FETCHING TEAMS

There was an error fetching the user's Yahoo Fantasy teams: {e}

Your response MUST:
1. Apologize for the technical issue
2. Ask them to try again in a moment
3. If the problem persists, they should check their Yahoo Fantasy account

Do NOT proceed with their request."""
        return ValidationResult(system_message=system_message)


def _handle_ambiguous_team_selection(user_teams: list[dict[str, str]]) -> ValidationResult:
    """Handle case where user has multiple teams but context is unclear."""
    teams_list = "\n".join(
        [f"- {team['team_name']} in {team['league_name']}" for team in user_teams]
    )
    system_message = f"""TEAM CLARIFICATION NEEDED

The user has multiple teams but you cannot determine which one they're asking about.

Their teams:
{teams_list}

Your response MUST:
Ask them to clarify which team they're referring to.

Do NOT proceed with their request until you know which team."""

    return ValidationResult(system_message=system_message)


def _handle_validated_context(league_id: str, team_id: str) -> ValidationResult:
    """Handle case where all validation checks have passed."""
    return ValidationResult(
        system_message="Context validated. Proceed with the user's request.",
        league_id=league_id,
        team_id=team_id,
    )


def validate_and_build_system_message(
    state: AgentState, memory_store: BaseStore
) -> ValidationResult:
    """
    Validate user context through a series of checks.

    This function runs through the validation pipeline:
    1. Email validation
    2. Authentication check
    3. Team availability check
    4. Team resolution
    5. Final validation

    Returns:
        ValidationResult containing system_message, league_id, and team_id
    """
    user_email, thread_id = _extract_user_info(state)
    if not user_email:
        return _handle_missing_email()

    has_oauth = _check_oauth_status(user_email)
    is_first_time = _is_first_time_user(user_email, memory_store)

    if is_first_time or not has_oauth:
        return _handle_first_time_or_no_oauth(user_email, thread_id, is_first_time, has_oauth)

    repo = YahooUserTeamRepository()
    try:
        user_teams = repo.get_user_teams_with_league_info(user_email)
    finally:
        repo.close()
    if not user_teams:
        return _handle_no_teams_in_db(user_email)

    league_id, team_id = _resolve_team_context(state, user_teams)
    if not league_id or not team_id:
        return _handle_ambiguous_team_selection(user_teams)

    return _handle_validated_context(league_id, team_id)
