"""Context validation for agent initialization.

This module validates user context (first-time user, team availability, etc.)
and returns system message instructions for Gordie.
"""

import ast
import logging

from agent.agent_state import AgentState, get_user_teams
from langgraph.store.base import BaseStore
from server.oauth import load_tokens_from_db
from tools.oauth.generate_oauth_link import generate_oauth_link
from tools.yahoo.get_user_leagues import get_user_leagues

logger = logging.getLogger(__name__)


def _sanitize_namespace_label(label: str) -> str:
    """Sanitize a string for use in LangGraph store namespace."""
    return label.replace(".", "_dot_").replace("@", "_at_")


def _is_first_time_user(user_email: str, memory_store: BaseStore) -> bool:
    """
    Check if this user has ever messaged Gordie before.

    Checks the memory store for any past conversations with this user.
    """
    try:
        safe_email = _sanitize_namespace_label(user_email)
        namespace = ("memories", safe_email)
        results = memory_store.search(namespace, query="", limit=1)

        if results and len(results) > 0:
            logger.info(f"User {user_email} has past conversations")
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
    # Check for team_context in last message
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

    # Check state for existing league_id/team_id
    if state.get("league_id") and state.get("team_id"):
        return state.get("league_id"), state.get("team_id")

    # Only one team - auto-assign
    if len(user_teams) == 1:
        team = user_teams[0]
        return team["league_id"], team["team_id"]

    return None, None


def validate_and_build_system_message(
    state: AgentState, memory_store: BaseStore
) -> tuple[str, str | None, str | None]:
    """
    Validate user context and build system message instructions for Gordie.

    This runs deterministic checks and returns a system message that tells Gordie
    what to do based on the validation results.

    Returns:
        Tuple of (system_message, league_id, team_id)
        - system_message: Instructions for Gordie
        - league_id: Resolved league ID or None
        - team_id: Resolved team ID or None
    """
    user_email = state.get("user_email", "")
    thread_id = state.get("thread_id", "")

    if not user_email:
        return (
            "Error: No user email found. Tell the user there was an error and to try again.",
            None,
            None,
        )

    # Check if user has OAuth tokens
    user_tokens = load_tokens_from_db(user_email)
    has_oauth = user_tokens is not None

    # Get user's teams
    user_teams = get_user_teams(user_email)

    # Check if first-time user
    is_first_time = _is_first_time_user(user_email, memory_store)

    # First-time user OR user without OAuth tokens
    if is_first_time or not has_oauth:
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

        return system_message, None, None

    # User is authenticated but has no teams in database
    # Fetch their available teams from Yahoo and present them deterministically
    if not user_teams:
        logger.info(f"User {user_email} is authenticated but has no teams. Fetching available teams from Yahoo.")

        try:
            # Call get_user_leagues to fetch available teams
            available_teams_str = get_user_leagues.invoke({"user_email": user_email})

            # Parse the string representation of the list
            available_teams = ast.literal_eval(available_teams_str)

            if not available_teams:
                system_message = """NO TEAMS AVAILABLE

The user has authenticated with Yahoo but has no Fantasy Hockey teams.

Your response MUST:
1. Explain that they don't have any Yahoo Fantasy Hockey teams
2. Tell them to create a team on Yahoo Fantasy first
3. Once they have a team, they can come back and you'll help them onboard

Do NOT proceed with their request."""
                return system_message, None, None

            # Filter to only hockey teams (game_code='nhl')
            hockey_teams = [team for team in available_teams if team.get('sport') == 'nhl']

            if not hockey_teams:
                system_message = """NO HOCKEY TEAMS AVAILABLE

The user has authenticated with Yahoo but has no Fantasy Hockey teams (only other sports).

Your response MUST:
1. Explain that they don't have any Yahoo Fantasy Hockey teams
2. Tell them to create a hockey team on Yahoo Fantasy first
3. Once they have a hockey team, they can come back and you'll help them onboard

Do NOT proceed with their request."""
                return system_message, None, None

            # Build a formatted list of teams
            teams_list = []
            for team in hockey_teams:
                active_status = "Active" if team.get('is_active', False) else "Off-season"
                team_str = (
                    f"  - Team: {team['team_name']}\n"
                    f"    Season: {team['season']} ({active_status})\n"
                    f"    game_key={team['game_key']}, league_id={team['league_id']}, team_id={team['team_id']}"
                )
                teams_list.append(team_str)

            teams_formatted = "\n\n".join(teams_list)

            system_message = f"""SELECT TEAM TO ONBOARD

The user has authenticated with Yahoo. Here are their available Fantasy Hockey teams:

{teams_formatted}

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

            return system_message, None, None

        except Exception as e:
            logger.error(f"Error fetching available teams for {user_email}: {e}")
            system_message = f"""ERROR FETCHING TEAMS

There was an error fetching the user's Yahoo Fantasy teams: {e}

Your response MUST:
1. Apologize for the technical issue
2. Ask them to try again in a moment
3. If the problem persists, they should check their Yahoo Fantasy account

Do NOT proceed with their request."""
            return system_message, None, None

    # Resolve team context
    league_id, team_id = _resolve_team_context(state, user_teams)

    # Multiple teams but can't determine which one
    if not league_id or not team_id:
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

        return system_message, None, None

    # All checks passed
    system_message = "Context validated. Proceed with the user's request."

    return system_message, league_id, team_id
