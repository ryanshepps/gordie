"""Shared agent state and utility functions."""

import logging
from typing import Annotated, Any, Literal

from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from client.duck_db_client import get_platform_db_connection

logger = logging.getLogger(__name__)


class TeamInferenceResult(BaseModel):
    """Structured output for team inference from user message."""

    team_index: int | None = Field(
        None,
        description=(
            "1-based index of the inferred team "
            "(e.g., 1 for first team, 2 for second). None if unclear."
        ),
    )
    is_unclear: bool = Field(
        description="True if the message is ambiguous and team cannot be determined"
    )
    reasoning: str = Field(
        description="Brief explanation of why this team was selected or why it's unclear"
    )


# Type alias for team_context format: app:game_key:league_id:team_id
# Example: "Yahoo:123:456:789" or "ESPN:nfl.l.123456:456:789"
TeamContext = Annotated[
    str,
    "Format: app:game_key:league_id:team_id where app is 'Yahoo' or 'ESPN', "
    "game_key is string/int, league_id and team_id are integers",
]


# JumpTo type matches langchain's middleware types
JumpTo = Literal["tools", "model", "end"]


class _AgentStateRequired(TypedDict):
    """Required fields for AgentState."""

    messages: Annotated[list[Any], add_messages]  # List of message objects or dicts


class AgentState(_AgentStateRequired, total=False):
    """Agent state with required messages and optional custom fields."""

    # Optional fields from langchain's AgentState
    jump_to: JumpTo | None  # Used by middleware for flow control
    structured_response: Any  # Used by middleware for structured output
    # Custom fields
    user_email: str
    league_id: str | None
    team_id: str | None
    thread_id: str
    has_teams: bool
    user_teams: list[dict[str, str]]  # List of all user's teams
    response: str | None
    route_to: str | None  # Target agent for routing (e.g., "player_comparison")
    # Flow tracking fields
    agent_flow: list[str]  # Ordered sequence: ["onboarding", "player_comparison"]
    current_agent_index: int  # Current position in flow (0-based)
    flow_complete: bool  # Explicit completion flag
    flow_reasoning: str | None  # LLM reasoning for agent flow decision
    # Email threading fields
    original_subject: str | None  # Original email subject for reply threading
    original_message: str | None  # Original user message for quoting in replies


def get_user_teams(user_email: str) -> list[dict[str, str]]:
    """Query database to get all teams for a user."""
    conn = get_platform_db_connection()
    try:
        result = conn.execute(
            """
            SELECT
                yut.league_id,
                yut.team_id,
                yut.team_name,
                yl.game_key,
                yl.league_name
            FROM yahoo_user_teams yut
            JOIN yahoo_leagues yl ON yut.league_id = yl.league_id
            WHERE yut.user_email = ?
        """,
            [user_email],
        ).fetchall()

        teams = []
        for row in result:
            teams.append(
                {
                    "league_id": str(row[0]),
                    "team_id": str(row[1]),
                    "team_name": str(row[2]),
                    "game_key": str(row[3]),
                    "league_name": str(row[4]),
                }
            )
        return teams
    finally:
        conn.close()


def infer_team_from_context(
    user_teams: list[dict[str, str]], last_message: str
) -> dict[str, str] | None:
    """Use LLM to infer which team the user is referring to based on message and teams."""
    from typing import cast

    if not user_teams:
        return None

    if len(user_teams) == 1:
        # Only one team, use it automatically
        return {
            "team": str(user_teams[0]),
            "confidence": "high",
            "reasoning": "User only has one team",
        }

    # Use LLM with structured output to infer team from message
    model = ChatOpenAI(model="gpt-5-nano-2025-08-07")
    structured_llm = model.with_structured_output(TeamInferenceResult, method="function_calling")

    teams_description = "\n".join(
        [
            f"{i + 1}. Team: {team['team_name']}, League: {team['league_name']}, "
            f"Game: {team['game_key']}"
            for i, team in enumerate(user_teams)
        ]
    )

    prompt = f"""Based on the user's message and their available teams, determine which team \
they are referring to.

User's message: "{last_message}"

User's teams:
{teams_description}

Analyze the message and determine:
1. If the message clearly refers to a specific team, provide the team_index \
(1-{len(user_teams)}) and set is_unclear to False
2. If the message is ambiguous and you cannot determine which team, set is_unclear to True \
and team_index to None
3. Always provide reasoning for your decision

Examples:
- If the user mentions a specific team name or league name that matches one team, select it
- If the user's message doesn't contain enough context to determine the team, mark as unclear
- If the user mentions players, league context, or team-specific details, use that to infer"""

    result = cast(TeamInferenceResult, structured_llm.invoke(prompt))

    # Parse structured response
    if result.is_unclear or result.team_index is None:
        return None

    # Convert 1-based index to 0-based
    team_index = result.team_index - 1
    if 0 <= team_index < len(user_teams):
        return {
            "team": str(user_teams[team_index]),
            "confidence": "medium",
            "reasoning": result.reasoning,
        }

    return None


def build_context(
    team_context: TeamContext, last_message: str, user_email: str
) -> dict[str, str | bool | None]:
    """Build context from team_context. Query database and use LLM inference if needed."""
    parts = team_context.split(":")

    # Handle case where team_context doesn't have all 4 parts
    app = parts[0] if len(parts) > 0 else None
    game_key = parts[1] if len(parts) > 1 and parts[1] else None
    league_id = parts[2] if len(parts) > 2 and parts[2] else None
    team_id = parts[3] if len(parts) > 3 and parts[3] else None

    if app and app not in ["Yahoo", "ESPN"]:
        raise ValueError(f"Invalid app: {app}")

    # Check if any context is missing
    if not all([app, game_key, league_id, team_id]):
        logger.info(
            "Missing context in team_context. Attempting to infer from database and message."
        )

        # Get all user teams from database
        user_teams = get_user_teams(user_email)

        if not user_teams:
            # No teams found - need to ask user to onboard
            return {
                "league_id": None,
                "team_id": None,
                "needs_clarification": True,
                "clarification_message": (
                    "I couldn't find any teams associated with your account. "
                    "Would you like to onboard a team first?"
                ),
            }

        # Try to infer team from message context
        inference_result = infer_team_from_context(user_teams, last_message)

        if inference_result:
            # Successfully inferred team
            inferred_team_str = inference_result["team"]
            # Parse the team dict from string representation if needed
            # For now, assume we need to get team data from user_teams
            for team in user_teams:
                team_name = team.get("team_name")
                if str(team) == inferred_team_str or (team_name and team_name in inferred_team_str):
                    return {
                        "league_id": team["league_id"],
                        "team_id": team["team_id"],
                        "needs_clarification": False,
                    }

        # Cannot determine team - ask user to specify
        teams_list = "\n".join(
            [
                f"{i + 1}. {team['team_name']} (League: {team['league_name']})"
                for i, team in enumerate(user_teams)
            ]
        )

        return {
            "league_id": None,
            "team_id": None,
            "needs_clarification": True,
            "clarification_message": (
                f"I found multiple teams for your account. Which team are you asking about?"
                f"\n\n{teams_list}\n\nPlease specify which team you're referring to."
            ),
        }

    return {
        "league_id": league_id,
        "team_id": team_id,
        "needs_clarification": False,
    }
