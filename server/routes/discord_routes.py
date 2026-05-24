"""Discord HTTP interaction route handler."""

import json
import logging
import os
import threading
import time
from collections.abc import Mapping, Sequence
from typing import cast

from quart import Quart, jsonify, request

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
    mode = os.getenv("DISCORD_MODE", "interactions").strip().lower()
    return mode != "gateway" and bool(
        os.getenv("DISCORD_PUBLIC_KEY") and os.getenv("DISCORD_APPLICATION_ID")
    )


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
        from server.adapters.discord_adapter import send_discord_text
        from server.discord_message_processor import process_discord_message

        def upsert_interaction_target(thread_id: str) -> None:
            target_repo = DiscordInteractionRepository()
            try:
                target_repo.upsert_target(thread_id, application_id, interaction_token)
            finally:
                target_repo.close()

        _ = process_discord_message(
            discord_user_id=discord_user_id,
            display_name=display_name,
            message_body=message_body,
            inbound_message_id=interaction_id,
            send_text=send_discord_text,
            logger=logger,
            dispatch_agent_response=True,
            on_thread_resolved=upsert_interaction_target,
        )
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
