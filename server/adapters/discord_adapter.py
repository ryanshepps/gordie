"""Discord channel adapter."""

from dataclasses import dataclass

from agent.agent_state import AgentState
from data.models import Medium
from module.logger import get_logger
from server.adapters.base import ChannelConstraints, MessageFormat

logger = get_logger(__name__)


def send_discord_text(thread_id: str, text: str) -> None:
    """Send text to the latest Discord interaction target for a thread."""
    from data.discord_interaction_repository import DiscordInteractionRepository

    repo = DiscordInteractionRepository()
    try:
        target = repo.get_target(thread_id)
    finally:
        repo.close()

    if target is None:
        logger.error(f"Could not resolve Discord interaction target for thread_id: {thread_id}")
        return

    from server.discord_service import DiscordService

    result = DiscordService().edit_original_response(
        target.application_id,
        target.interaction_token,
        text,
    )
    if result.success:
        logger.info(f"Discord response sent for thread_id: {thread_id}")
    else:
        logger.error(f"Failed to send Discord response for thread_id {thread_id}: {result.error}")


@dataclass(frozen=True, slots=True)
class DiscordAdapter:
    medium: Medium = Medium.DISCORD

    @property
    def constraints(self) -> ChannelConstraints:
        return ChannelConstraints(max_length=2000, message_format=MessageFormat.MARKDOWN)

    def send(self, external_id: str, text: str, state: AgentState) -> None:
        thread_id = state.get("thread_id")
        if not thread_id:
            logger.error(f"No thread_id in state, cannot send Discord response to {external_id}")
            return

        send_discord_text(thread_id, text)
