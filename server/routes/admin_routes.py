"""Admin API routes for observability dashboard."""

import os
from functools import wraps
from typing import Any

from flask import Flask, jsonify, request
from sqlalchemy import text

from agent.memory_store import get_conversation_summaries_by_email
from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)

_ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")


def _require_admin_key(f):
    """Decorator that validates the X-Admin-Key header."""

    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-Admin-Key", "")
        if not _ADMIN_KEY or provided_key != _ADMIN_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated


def _extract_messages_from_checkpoint(thread_id: str) -> list[dict[str, Any]]:
    """Read LangGraph checkpoint data and extract human/AI message pairs.

    Args:
        thread_id: The conversation thread ID

    Returns:
        List of message dicts with role, content, and timestamp
    """
    session = get_session()
    try:
        # langgraph-checkpoint-postgres stores checkpoints in a 'checkpoints' table
        rows = session.execute(
            text(
                """
                SELECT type, checkpoint
                FROM checkpoints
                WHERE thread_id = :thread_id
                ORDER BY checkpoint_id DESC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id},
        ).fetchall()

        if not rows:
            return []

        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        serde = JsonPlusSerializer()
        checkpoint_data: dict[str, Any] = serde.loads_typed((rows[0][0], rows[0][1]))

        channel_values = checkpoint_data.get("channel_values", {})
        messages_raw: list[Any] = channel_values.get("messages", [])

        messages: list[dict[str, Any]] = []
        for msg in messages_raw:
            role: str | None = None
            content = ""
            timestamp = ""

            if hasattr(msg, "type"):
                if msg.type == "human":
                    role = "human"
                elif msg.type == "ai":
                    role = "ai"
                content = str(msg.content) if hasattr(msg, "content") else ""
            elif isinstance(msg, dict):
                msg_type = msg.get("type") or msg.get("role", "")
                if msg_type in ("human", "user"):
                    role = "human"
                elif msg_type in ("ai", "assistant"):
                    role = "ai"
                content = msg.get("content", "")

            if not role or not content:
                continue

            if isinstance(content, list):
                continue

            additional_kwargs: dict[str, Any] = getattr(msg, "additional_kwargs", {})
            response_metadata: dict[str, Any] = getattr(msg, "response_metadata", {})
            timestamp = additional_kwargs.get("timestamp", "") or response_metadata.get(
                "timestamp", ""
            )

            messages.append({"role": role, "content": content, "timestamp": timestamp})

        return messages

    except Exception as e:
        logger.error(f"Failed to extract messages from checkpoint: {e}")
        return []
    finally:
        session.close()


def register_admin_routes(app: Flask) -> None:
    """Register admin API routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/admin/conversations", methods=["GET"])
    @_require_admin_key
    def get_conversations():
        """Get conversation summaries for a user."""
        email = request.args.get("email")
        if not email:
            return jsonify({"error": "email query parameter is required"}), 400

        summaries = get_conversation_summaries_by_email(email)
        return jsonify(summaries), 200

    @app.route("/admin/conversations/<path:thread_id>/messages", methods=["GET"])
    @_require_admin_key
    def get_conversation_messages(thread_id: str):
        """Get full message history for a conversation thread."""
        messages = _extract_messages_from_checkpoint(thread_id)

        # Derive user_email from thread_id (format: "user@example.com:c742739921c2")
        user_email = thread_id.split(":")[0] if ":" in thread_id else ""

        return jsonify(
            {
                "thread_id": thread_id,
                "user_email": user_email,
                "messages": messages,
            }
        ), 200
