"""Discord interaction webhook response service."""

from dataclasses import dataclass

import requests

from module.logger import get_logger

logger = get_logger(__name__)

DISCORD_WEBHOOK_BASE_URL = "https://discord.com/api/webhooks"
DISCORD_MAX_CONTENT_LENGTH = 2000
DISCORD_TRUNCATION_NOTICE = "\n\n[Response truncated for Discord. Ask Gordie to narrow the question for more detail.]"


def _fit_discord_content(content: str) -> str:
    """Constrain outbound content to Discord's message limit."""
    if len(content) <= DISCORD_MAX_CONTENT_LENGTH:
        return content

    max_body_length = DISCORD_MAX_CONTENT_LENGTH - len(DISCORD_TRUNCATION_NOTICE)
    return f"{content[:max_body_length].rstrip()}{DISCORD_TRUNCATION_NOTICE}"


@dataclass(frozen=True, slots=True)
class DiscordResult:
    """Result of editing a Discord interaction response."""

    success: bool
    error: str | None = None


class DiscordService:
    """Service for editing Discord interaction responses."""

    def edit_original_response(
        self,
        application_id: str,
        interaction_token: str,
        content: str,
    ) -> DiscordResult:
        """Edit the original deferred Discord interaction response."""
        url = f"{DISCORD_WEBHOOK_BASE_URL}/{application_id}/{interaction_token}/messages/@original"
        payload: dict[str, object] = {
            "content": _fit_discord_content(content),
            "allowed_mentions": {"parse": []},
        }

        try:
            response = requests.patch(url, json=payload, timeout=10)
            if 400 <= response.status_code < 500:
                logger.error(f"Discord API 4xx error: {response.status_code} {response.text}")
                return DiscordResult(success=False, error=f"Client error: {response.status_code}")

            response.raise_for_status()
            logger.info(f"Discord response edited for application_id={application_id}")
            return DiscordResult(success=True)
        except requests.exceptions.RequestException as exc:
            logger.error(f"Failed to edit Discord response: {exc}")
            return DiscordResult(success=False, error=str(exc))
