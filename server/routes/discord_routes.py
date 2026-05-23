"""Discord HTTP interaction route handler."""

import json
import logging
import os
import threading
import time
from collections.abc import Mapping, Sequence
from typing import cast

from quart import Quart, jsonify, request

from data.models import Medium
from module.logger import get_logger
from server.webhook_verification import verify_discord_interaction

JsonMapping = Mapping[str, object]

DISCORD_PING = 1
DISCORD_APPLICATION_COMMAND = 2
DISCORD_PONG_RESPONSE = 1
DISCORD_DEFERRED_CHANNEL_MESSAGE = 5


def _as_mapping(value: object) -> JsonMapping | None:
    if isinstance(value, Mapping):
        return cast(JsonMapping, value)
    return None


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return value
    return ()


def _get_str(mapping: JsonMapping, key: str) -> str | None:
    value = mapping.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _extract_user(payload: JsonMapping) -> tuple[str | None, str | None]:
    member = _as_mapping(payload.get("member"))
    user = _as_mapping(member.get("user")) if member else None
    if user is None:
        user = _as_mapping(payload.get("user"))
    if user is None:
        return None, None

    user_id = _get_str(user, "id")
    display_name = _get_str(user, "global_name") or _get_str(user, "username")
    return user_id, display_name


def _extract_command_text(payload: JsonMapping) -> str | None:
    data = _as_mapping(payload.get("data"))
    if data is None or _get_str(data, "name") != "gordie":
        return None

    fallback: str | None = None
    for option_value in _as_sequence(data.get("options")):
        option = _as_mapping(option_value)
        if option is None:
            continue
        value = _get_str(option, "value")
        if value is None:
            continue
        if fallback is None:
            fallback = value
        if _get_str(option, "name") == "question":
            return value
    return fallback


def _validate_application_id(application_id: str) -> bool:
    expected = os.getenv("DISCORD_APPLICATION_ID")
    return expected == application_id


def _discord_configured() -> bool:
    return bool(os.getenv("DISCORD_PUBLIC_KEY") and os.getenv("DISCORD_APPLICATION_ID"))


def register_discord_routes(app: Quart) -> None:
    """Register Discord interaction routes on the Quart app."""

    @app.route("/discord/interactions", methods=["POST"])
    async def discord_interactions():  # pyright: ignore[reportUnusedFunction]
        """Handle incoming Discord HTTP interactions."""
        start_time = time.time()
        logger = get_logger(__name__, log_file="server.log")

        if not _discord_configured():
            return jsonify({"error": "Discord not configured"}), 503

        raw_data = await request.get_data()
        raw_body = raw_data.encode("utf-8") if isinstance(raw_data, str) else raw_data
        signature = request.headers.get("X-Signature-Ed25519", "")
        timestamp = request.headers.get("X-Signature-Timestamp", "")

        if not signature or not timestamp:
            return jsonify({"error": "Missing signature"}), 401

        if not verify_discord_interaction(signature, timestamp, raw_body):
            return jsonify({"error": "Invalid signature"}), 401

        try:
            payload_obj = cast(object, json.loads(raw_body.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return jsonify({"error": "Invalid JSON"}), 400

        payload = _as_mapping(payload_obj)
        if payload is None:
            return jsonify({"error": "Invalid payload"}), 400

        interaction_type = payload.get("type")
        if interaction_type == DISCORD_PING:
            return jsonify({"type": DISCORD_PONG_RESPONSE}), 200

        if interaction_type != DISCORD_APPLICATION_COMMAND:
            return jsonify({"error": "Unsupported interaction"}), 400

        application_id = _get_str(payload, "application_id")
        interaction_token = _get_str(payload, "token")
        interaction_id = _get_str(payload, "id")
        discord_user_id, display_name = _extract_user(payload)
        message_body = _extract_command_text(payload)

        if not all(
            [application_id, interaction_token, interaction_id, discord_user_id, message_body]
        ):
            return jsonify({"error": "Missing required fields"}), 400

        assert application_id is not None
        assert interaction_token is not None
        assert interaction_id is not None
        assert discord_user_id is not None
        assert message_body is not None

        if not _validate_application_id(application_id):
            return jsonify({"error": "Wrong application"}), 403

        def process_discord() -> None:
            _process_discord_interaction(
                application_id=application_id,
                interaction_token=interaction_token,
                interaction_id=interaction_id,
                discord_user_id=discord_user_id,
                display_name=display_name,
                message_body=message_body,
                logger=logger,
            )

        threading.Thread(
            target=process_discord,
            daemon=True,
            name=f"discord-{interaction_id[:8]}",
        ).start()

        duration = time.time() - start_time
        logger.info(f"Deferred Discord interaction in {duration:.3f}s")
        return jsonify({"type": DISCORD_DEFERRED_CHANNEL_MESSAGE}), 200


def _process_discord_interaction(
    application_id: str,
    interaction_token: str,
    interaction_id: str,
    discord_user_id: str,
    display_name: str | None,
    message_body: str,
    logger: logging.Logger,
) -> None:
    try:
        from data.discord_interaction_repository import DiscordInteractionRepository
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

        target_repo = DiscordInteractionRepository()
        try:
            target_repo.upsert_target(thread_id, application_id, interaction_token)
        finally:
            target_repo.close()

        processed_repo = ProcessedInboundMessageRepository()
        try:
            if not processed_repo.claim(Medium.DISCORD, interaction_id, discord_user_id):
                logger.info(f"Duplicate Discord interaction {interaction_id}, skipping")
                return
        finally:
            processed_repo.close()

        if not user_email:
            from server.adapters.discord_adapter import send_discord_text
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
            send_discord_text(thread_id, oauth_message)
            logger.info(f"Sent cold-start OAuth Discord response to {discord_user_id}")
            return

        from billing import get_gateway

        gateway = get_gateway()
        billing_ctx = None
        allowed, reason = gateway.check_question_allowed(user_email, message_body)
        if not allowed:
            billing_ctx = gateway.build_billing_context(user_email, reason, Medium.DISCORD)

        from scripts.message_agent import message_agent

        _ = message_agent(
            message=message_body,
            thread_id=thread_id,
            channel=Medium.DISCORD,
            user_id=str(user_id),
            external_id=discord_user_id,
            billing_context=billing_ctx,
        )
        logger.info(f"Agent processing complete for Discord user {discord_user_id}")
    except Exception as exc:
        logger.error(
            f"Error processing Discord interaction from {discord_user_id}: {exc}",
            exc_info=True,
        )
        error_message = "Gordie hit an error while processing that. Try again in a minute."
        from server.discord_service import DiscordService

        _ = DiscordService().edit_original_response(
            application_id,
            interaction_token,
            error_message,
        )
