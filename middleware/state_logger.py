"""Middleware for logging AgentState at key points in the agent flow."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState as BaseAgentState
from langgraph.runtime import Runtime

from module.logger import get_logger

logger = get_logger(__name__)

# Type alias for the base AgentState with Any response type
_BaseState = BaseAgentState[Any]


def _format_state(state: _BaseState) -> str:
    """Format AgentState dict into a readable log string."""
    # Fields to skip (too verbose or not useful)
    skip_fields = {"messages", "user_teams", "persona"}

    state_parts = []
    for field, value in state.items():
        if field in skip_fields or value is None:
            continue

        # Truncate long strings
        if isinstance(value, str) and len(value) > 50:
            value = value[:50] + "..."
        elif isinstance(value, list) and len(value) > 5:
            value = f"[{len(value)} items]"

        state_parts.append(f"{field}={value}")

    return ", ".join(state_parts) if state_parts else "empty_state"


class StateLoggingMiddleware(AgentMiddleware[_BaseState, Any]):
    """Middleware that logs AgentState before and after model calls."""

    def __init__(self, agent_name: str = "agent"):
        """
        Initialize the middleware.

        Args:
            agent_name: Name to identify which agent is logging (e.g., "controller", "onboarding")
        """
        self.agent_name = agent_name

    def before_model(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state before each model call."""
        # Debug: log raw state keys and types
        logger.info(f"[{self.agent_name}:DEBUG] state type: {type(state)}, keys: {list(state.keys())}")
        state_str = _format_state(state)
        logger.info(f"[{self.agent_name}:BEFORE_MODEL] {state_str}")
        return None

    def after_model(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state after each model call."""
        state_str = _format_state(state)
        logger.info(f"[{self.agent_name}:AFTER_MODEL] {state_str}")
        return None

    def before_agent(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state when agent execution starts."""
        state_str = _format_state(state)
        logger.info(f"[{self.agent_name}:AGENT_START] {state_str}")
        return None

    def after_agent(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state when agent execution completes."""
        state_str = _format_state(state)
        logger.info(f"[{self.agent_name}:AGENT_END] {state_str}")
        return None
