"""Discord Gateway client for local self-hosted chat."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass

import discord

from module.logger import get_logger
from server.discord_message_processor import process_discord_message
from server.discord_service import fit_discord_content

logger = get_logger(__name__)

DISCORD_MODE_GATEWAY = "gateway"
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class DiscordGatewayConfig:
    """Runtime settings for the Discord Gateway client."""

    bot_token: str
    allowed_user_ids: frozenset[str]
    require_mention: bool


def discord_gateway_enabled() -> bool:
    """Return whether the local Discord Gateway client should run."""
    mode = os.getenv("DISCORD_MODE", "").strip().lower()
    explicit_enabled = os.getenv("DISCORD_GATEWAY_ENABLED", "").strip().lower()
    if explicit_enabled in _TRUE_VALUES:
        return True

    chat_media = {
        value.strip().lower() for value in os.getenv("CHAT_MEDIA", "").split(",") if value.strip()
    }
    return mode == DISCORD_MODE_GATEWAY and "discord" in chat_media


def load_gateway_config() -> DiscordGatewayConfig:
    """Load and validate Discord Gateway settings from the environment."""
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("DISCORD_BOT_TOKEN is required when DISCORD_MODE=gateway")

    allowed_user_ids = parse_allowed_user_ids(os.getenv("DISCORD_ALLOWED_USER_IDS", ""))
    if not allowed_user_ids:
        raise ValueError("DISCORD_ALLOWED_USER_IDS is required when DISCORD_MODE=gateway")

    require_mention = os.getenv("DISCORD_REQUIRE_MENTION", "true").strip().lower() in _TRUE_VALUES
    return DiscordGatewayConfig(
        bot_token=bot_token,
        allowed_user_ids=frozenset(allowed_user_ids),
        require_mention=require_mention,
    )


def parse_allowed_user_ids(raw_value: str) -> tuple[str, ...]:
    """Parse a comma-separated allowlist of Discord user IDs."""
    seen: set[str] = set()
    user_ids: list[str] = []
    for value in raw_value.split(","):
        user_id = value.strip()
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        user_ids.append(user_id)
    return tuple(user_ids)


def extract_gateway_message_body(
    content: str,
    *,
    bot_user_id: str | None,
    require_mention: bool,
    is_direct_message: bool,
) -> str | None:
    """Return the user question that should be sent to Gordie, if any."""
    body = content.strip()
    if not body:
        return None

    if is_direct_message or not require_mention:
        return body

    if bot_user_id is None:
        return None

    mention_tokens = (f"<@{bot_user_id}>", f"<@!{bot_user_id}>")
    if not any(token in body for token in mention_tokens):
        return None

    for token in mention_tokens:
        body = body.replace(token, "")
    body = body.strip()
    return body or None


class GordieDiscordClient(discord.Client):
    """Discord client that forwards allowed user messages into Gordie."""

    def __init__(self, config: DiscordGatewayConfig) -> None:
        intents = discord.Intents.default()
        intents.messages = True
        intents.dm_messages = True
        intents.guild_messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self._config: DiscordGatewayConfig = config

    async def on_ready(self) -> None:
        """Log readiness after Discord accepts the Gateway session."""
        user = self.user
        logger.info(f"Discord Gateway connected as {user}")

    async def on_message(self, message: discord.Message) -> None:
        """Forward allowed Discord messages into the normal Gordie flow."""
        if message.author.bot:
            return

        discord_user_id = str(message.author.id)
        if discord_user_id not in self._config.allowed_user_ids:
            logger.info(f"Ignoring Discord message from unallowed user {discord_user_id}")
            return

        bot_user_id = str(self.user.id) if self.user else None
        body = extract_gateway_message_body(
            message.content,
            bot_user_id=bot_user_id,
            require_mention=self._config.require_mention,
            is_direct_message=isinstance(message.channel, discord.DMChannel),
        )
        if body is None:
            return

        display_name = message.author.global_name or message.author.name
        loop = asyncio.get_running_loop()

        def send_text(_thread_id: str, text: str) -> None:
            future = asyncio.run_coroutine_threadsafe(
                message.channel.send(
                    fit_discord_content(text), allowed_mentions=discord.AllowedMentions.none()
                ),
                loop,
            )
            _ = future.result(timeout=30)

        try:
            async with message.channel.typing():
                result = await asyncio.to_thread(
                    process_discord_message,
                    discord_user_id=discord_user_id,
                    display_name=display_name,
                    message_body=body,
                    inbound_message_id=str(message.id),
                    send_text=send_text,
                    logger=logger,
                )
            if result.status == "empty_response":
                _ = await message.channel.send(
                    "Gordie did not produce a response. Try again in a minute.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except Exception as exc:
            logger.error(
                f"Error processing Discord Gateway message from {discord_user_id}: {exc}",
                exc_info=True,
            )
            _ = await message.channel.send(
                "Gordie hit an error while processing that. Try again in a minute.",
                allowed_mentions=discord.AllowedMentions.none(),
            )


def start_discord_gateway_in_background() -> threading.Thread | None:
    """Start the Discord Gateway client in a daemon thread when configured."""
    if not discord_gateway_enabled():
        logger.info("Discord Gateway mode disabled")
        return None

    config = load_gateway_config()

    def run_gateway() -> None:
        client = GordieDiscordClient(config)
        asyncio.run(client.start(config.bot_token))

    thread = threading.Thread(target=run_gateway, daemon=True, name="discord-gateway")
    thread.start()
    logger.info("Discord Gateway client starting")
    return thread
