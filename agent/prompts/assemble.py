from agent.agent_state import AgentState
from agent.context_resolvers import format_teams_for_display
from agent.context_types import ContextStatus
from agent.prompts.analyst_identity import ANALYST_IDENTITY
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.rules import RULES
from agent.prompts.sport_context import get_sport_context, get_sport_label


def _build_context_section(state: AgentState) -> str:
    user_email = state.get("user_email", "")
    context_status: ContextStatus = state.get("context_status", "error")

    parts = ["# CONTEXT", f"User email: {user_email}", ""]

    if context_status == "validated":
        parts.append("Context validated. Proceed with the user's request.")
        league_id = state.get("league_id")
        team_id = state.get("team_id")
        sport = state.get("sport")
        if league_id:
            parts.append(f"\nLeague ID: {league_id}")
        if team_id:
            parts.append(f"Team ID: {team_id}")
        if sport:
            parts.append(f"Sport: {sport}")

    elif context_status == "first_time_user":
        oauth_url = state.get("oauth_url", "")
        parts.append(f"""FIRST TIME USER DETECTED

This is the very first message from this user.

Your response MUST:
1. Introduce yourself as Gordie
2. Explain your capabilities (roster advice, trade analysis, player comparisons, waiver wire help)
3. Ask them to connect their Yahoo Fantasy team using this OAuth link: {oauth_url}
4. Be friendly and welcoming

Do NOT proceed with any fantasy-specific requests until they onboard.""")

    elif context_status == "no_oauth":
        oauth_url = state.get("oauth_url", "")
        parts.append(f"""NO OAUTH TOKENS

The user does not have valid Yahoo authentication.

Your response MUST:
1. Tell them they need to connect their Yahoo Fantasy account
2. Provide this OAuth link: {oauth_url}
3. Explain that you cannot help with fantasy requests until they authenticate

Do NOT proceed with their request.""")

    elif context_status == "no_teams_available":
        parts.append("""NO TEAMS AVAILABLE

The user has authenticated with Yahoo but has no supported Fantasy teams.

Your response MUST:
1. Explain that they don't have any supported Yahoo Fantasy teams
2. Tell them to join or create a team on Yahoo Fantasy first
3. Once they have a team, they can come back and you'll help them onboard

Do NOT proceed with their request.""")

    elif context_status == "team_selection_needed":
        available_teams = state.get("available_teams", [])
        formatted_teams = format_teams_for_display(available_teams)
        parts.append(f"""SELECT TEAM TO ONBOARD

The user has authenticated with Yahoo. Here are their available Fantasy teams:

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

Do NOT ask them for technical IDs - just ask which team/league name, then YOU extract the IDs from the list above.""")

    elif context_status == "team_ambiguous":
        available_teams = state.get("available_teams", [])
        teams_list = "\n".join(
            [f"- {team['team_name']} in {team['league_name']}" for team in available_teams]
        )
        parts.append(f"""TEAM CLARIFICATION NEEDED

The user has multiple teams but you cannot determine which one they're asking about.

Their teams:
{teams_list}

Your response MUST:
Ask them to clarify which team they're referring to.

Do NOT proceed with their request until you know which team.""")

    elif context_status == "auto_onboarded":
        sport_label = get_sport_label(state.get("sport"))
        league_id = state.get("league_id", "")
        team_id = state.get("team_id", "")
        parts.append(f"""TEAM AUTO-ONBOARDED

The user had one active {sport_label} team, which has been automatically set up.

Your response MUST:
1. Confirm their team has been connected
2. Ask what they need help with (trades, waivers, lineup advice, etc.)
3. Be enthusiastic and ready to help

Proceed with their original request if they had one.""")
        if league_id:
            parts.append(f"\nLeague ID: {league_id}")
        if team_id:
            parts.append(f"Team ID: {team_id}")

    elif context_status == "billing_blocked":
        billing_context = state.get("billing_context", "")
        parts.append(str(billing_context))

    elif context_status == "error":
        context_error = state.get("context_error", "Unknown error")
        parts.append(f"""ERROR

{context_error}

Your response MUST:
1. Apologize for the technical issue
2. Ask them to try again in a moment

Do NOT proceed with their request.""")

    return "\n".join(parts)


def assemble_system_prompt(state: AgentState) -> str:
    channel = state.get("channel", "email")
    sport = state.get("sport")
    channel_guidelines = get_channel_guidelines(channel)
    context_section = _build_context_section(state)
    sport_context = get_sport_context(sport)

    return f"{ANALYST_IDENTITY}\n{RULES}\n{channel_guidelines}\n\n{context_section}\n\n{sport_context}"
