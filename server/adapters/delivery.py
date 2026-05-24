"""Explicit response delivery helpers for transport boundary handlers."""

from agent.agent_state import AgentState
from data.models import Medium
from module.logger import get_logger
from server.adapters.registry import build_registry

logger = get_logger(__name__)


def deliver_agent_response(
    medium: Medium,
    external_id: str,
    text: str,
    state: AgentState,
) -> None:
    """Send agent text through the configured adapter for the inbound medium."""
    if not text.strip():
        logger.warning(f"No agent response to deliver for {medium.value}")
        return

    adapter = build_registry().get(medium)
    if adapter is None:
        logger.error(f"No adapter configured for channel: {medium.value}")
        return

    adapter.send(external_id, text, state)
