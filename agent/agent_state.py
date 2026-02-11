"""Shared agent state and utility functions."""

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from module.logger import get_logger

logger = get_logger(__name__)


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
    user_teams: list[dict[str, str]]  # List of all user's teams
    channel: str  # "email", "sms", or "web"
    has_rich_content: bool  # Set by tools that produce tabular/complex data
    response: str | None
    route_to: str | None  # Target agent for routing (e.g., "onboarding")
    # Flow tracking fields
    agent_flow: list[str]  # Ordered sequence of agents to execute
    current_agent_index: int  # Current position in flow (0-based)
    flow_complete: bool  # Explicit completion flag
    flow_reasoning: str | None  # LLM reasoning for agent flow decision
    # Email threading fields
    original_subject: str | None  # Original email subject for reply threading
    original_message: str | None  # Original user message for quoting in replies
