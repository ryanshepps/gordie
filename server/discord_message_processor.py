"""Shared Discord inbound message processing."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from data.models import Medium

SendDiscordText = Callable[[str, str], None]
ThreadResolvedCallback = Callable[[str], None]
DiscordProcessStatus = Literal["duplicate", "oauth_sent", "processed", "empty_response"]


@dataclass(frozen=True, slots=True)
class DiscordProcessResult:
    """Outcome of processing one Discord inbound message."""

    status: DiscordProcessStatus
    thread_id: str | None = None
    response_text: str | None = None


def process_discord_message(
    *,
    discord_user_id: str,
    display_name: str | None,
    message_body: str,
    inbound_message_id: str,
    send_text: SendDiscordText,
    logger: logging.Logger,
    dispatch_agent_response: bool,
    on_thread_resolved: ThreadResolvedCallback | None = None,
) -> DiscordProcessResult:
    """Process one Discord message from either HTTP interactions or Gateway."""

    from data.processed_inbound_message_repository import ProcessedInboundMessageRepository
    from data.thread_repository import ThreadRepository
    from data.user_repository import UserRepository

    user_repo = UserRepository()
    try:
        user_id = user_repo.resolve_user_id(
            Medium.DISCORD,
            discord_user_id,
            display_name or discord_user_id,
        )
        user_email = user_repo.get_identity_external_id(user_id, Medium.EMAIL)
    finally:
        user_repo.close()

    thread_repo = ThreadRepository()
    try:
        thread_info = thread_repo.resolve(user_id, Medium.DISCORD)
        thread_id = thread_info.thread_id
    finally:
        thread_repo.close()

    if on_thread_resolved is not None:
        on_thread_resolved(thread_id)

    processed_repo = ProcessedInboundMessageRepository()
    try:
        if not processed_repo.claim(Medium.DISCORD, inbound_message_id, discord_user_id):
            logger.info(f"Duplicate Discord message {inbound_message_id}, skipping")
            return DiscordProcessResult(status="duplicate", thread_id=thread_id)
    finally:
        processed_repo.close()

    if not user_email:
        from server.oauth_link_service import generate_cold_start_oauth_link

        oauth_url = generate_cold_start_oauth_link(
            Medium.DISCORD,
            discord_user_id,
            thread_id,
        )
        oauth_message = (
            "Hey, I'm Gordie - your fantasy sports guy.\n"
            f"Connect your Yahoo league here: {oauth_url}"
        )
        send_text(thread_id, oauth_message)
        logger.info(f"Sent cold-start OAuth Discord response to {discord_user_id}")
        return DiscordProcessResult(
            status="oauth_sent",
            thread_id=thread_id,
            response_text=oauth_message,
        )

    from billing import get_gateway

    gateway = get_gateway()
    billing_ctx = None
    allowed, reason = gateway.check_question_allowed(user_email, message_body)
    if not allowed:
        billing_ctx = gateway.build_billing_context(user_email, reason, Medium.DISCORD)

    from scripts.message_agent import message_agent

    response_text = message_agent(
        message=message_body,
        thread_id=thread_id,
        channel=Medium.DISCORD,
        user_id=str(user_id),
        external_id=discord_user_id,
        billing_context=billing_ctx,
        dispatch_response=dispatch_agent_response,
    )

    if not dispatch_agent_response and response_text:
        send_text(thread_id, response_text)

    if response_text:
        logger.info(f"Agent processing complete for Discord user {discord_user_id}")
        return DiscordProcessResult(
            status="processed",
            thread_id=thread_id,
            response_text=response_text,
        )

    logger.warning(f"Agent returned no Discord response for user {discord_user_id}")
    return DiscordProcessResult(status="empty_response", thread_id=thread_id)
