import logging
import os
import sqlite3
from typing import Annotated, cast

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from client.duck_db_client import get_platform_db_connection

logger = logging.getLogger(__name__)


class TeamInferenceResult(BaseModel):
    """Structured output for team inference from user message."""

    team_index: int | None = Field(
        None,
        description="1-based index of the inferred team (e.g., 1 for first team, 2 for second). None if unclear.",
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


class AgentState(TypedDict):
    persona: str
    user_email: str
    game_key: str | None
    league_id: str | None
    team_id: str | None
    thread_id: str
    messages: Annotated[list, add_messages]
    has_teams: bool
    user_teams: list[dict]  # List of all user's teams
    # intent: Optional[str]  # "onboarding", "player_assessment", "trade_waiver", "lineup_optimizer"
    team_inference: (
        dict | None
    )  # Result of team inference {"team": {...}, "confidence": str, "reasoning": str}
    needs_clarification: bool  # True if we need to ask user which team
    response: str | None


def get_user_teams(user_email: str) -> list[dict]:
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
                    "league_id": row[0],
                    "team_id": row[1],
                    "team_name": row[2],
                    "game_key": row[3],
                    "league_name": row[4],
                }
            )
        return teams
    finally:
        conn.close()


def is_first_message_in_thread(thread_id: str) -> bool:
    """
    Check if this is the first message in the current conversation thread.

    Args:
        thread_id: The conversation thread ID

    Returns:
        True if no previous checkpoints exist for this thread, False otherwise
    """
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )

    if not os.path.exists(db_path):
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM checkpoints
            WHERE thread_id = ?
        """,
            (thread_id,),
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count == 0

    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return True


def infer_team_from_context(user_teams: list[dict], last_message: str) -> dict | None:
    """Use LLM to infer which team the user is referring to based on their message and available teams."""
    if not user_teams:
        return None

    if len(user_teams) == 1:
        # Only one team, use it automatically
        return {"team": user_teams[0], "confidence": "high", "reasoning": "User only has one team"}

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

    prompt = f"""Based on the user's message and their available teams, determine which team they are referring to.

User's message: "{last_message}"

User's teams:
{teams_description}

Analyze the message and determine:
1. If the message clearly refers to a specific team, provide the team_index (1-{len(user_teams)}) and set is_unclear to False
2. If the message is ambiguous and you cannot determine which team, set is_unclear to True and team_index to None
3. Always provide reasoning for your decision

Examples:
- If the user mentions a specific team name or league name that matches one team, select that team
- If the user's message doesn't contain enough context to determine the team, mark as unclear
- If the user mentions players, league context, or team-specific details, use that to infer the team"""

    result = cast(TeamInferenceResult, structured_llm.invoke(prompt))

    # Parse structured response
    if result.is_unclear or result.team_index is None:
        return None

    # Convert 1-based index to 0-based
    team_index = result.team_index - 1
    if 0 <= team_index < len(user_teams):
        return {
            "team": user_teams[team_index],
            "confidence": "medium",
            "reasoning": result.reasoning,
        }

    return None


def build_context(team_context: TeamContext, last_message: str, user_email: str):
    """Build context from team_context. If any parts are missing, query database and use LLM inference."""
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
                "app": app,
                "game_key": None,
                "league_id": None,
                "team_id": None,
                "needs_clarification": True,
                "clarification_message": "I couldn't find any teams associated with your account. Would you like to onboard a team first?",
            }

        # Try to infer team from message context
        inference_result = infer_team_from_context(user_teams, last_message)

        if inference_result:
            # Successfully inferred team
            inferred_team = inference_result["team"]
            return {
                "app": "Yahoo",  # Assume Yahoo for now since that's what's in the DB
                "game_key": inferred_team["game_key"],
                "league_id": inferred_team["league_id"],
                "team_id": inferred_team["team_id"],
                "needs_clarification": False,
                "team_inference": inference_result,
            }
        else:
            # Cannot determine team - ask user to specify
            teams_list = "\n".join(
                [
                    f"{i + 1}. {team['team_name']} (League: {team['league_name']})"
                    for i, team in enumerate(user_teams)
                ]
            )

            return {
                "app": "Yahoo",
                "game_key": None,
                "league_id": None,
                "team_id": None,
                "needs_clarification": True,
                "clarification_message": f"I found multiple teams for your account. Which team are you asking about?\n\n{teams_list}\n\nPlease specify which team you're referring to.",
            }

    return {
        "app": app,
        "game_key": game_key,
        "league_id": league_id,
        "team_id": team_id,
        "needs_clarification": False,
    }


def build_agent_graph():
    """Build and return the agent graph with controller and sub-agents."""
    from agent.ControllerAgent import (
        clarification_node,
        controller_node,
        should_ask_for_clarification,
    )
    from agent.OnboardingAgent import agent as onboarding_agent

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("controller", controller_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node(
        "onboarding",
        lambda state: onboarding_agent.invoke(
            {"user_email": state["user_email"], "messages": state["messages"]}
        ),
    )

    # Set entry point
    workflow.set_entry_point("controller")

    # Add conditional edges from controller
    workflow.add_conditional_edges(
        "controller",
        should_ask_for_clarification,
        {
            "clarify": "clarification",
            "onboarding": "onboarding",
            "continue": END,  # For now, just end - will add more agents later
        },
    )

    # Clarification and onboarding end the conversation
    workflow.add_edge("clarification", END)
    workflow.add_edge("onboarding", END)

    # Setup persistent checkpointer
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # Compile the graph
    return workflow.compile(checkpointer=checkpointer)


# Build the agent graph
agent = build_agent_graph()
