"""Admin API routes for observability dashboard."""

import hmac
import os
from functools import wraps

from quart import Quart, jsonify, request

from agent.checkpoint_reader import get_messages_from_checkpoint
from agent.memory_store import get_conversation_summaries_by_email
from module.logger import get_logger

logger = get_logger(__name__)

_ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")


def _require_admin_key(f):
    """Decorator that validates the X-Admin-Key header."""

    @wraps(f)
    async def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-Admin-Key", "")
        if not _ADMIN_KEY or not hmac.compare_digest(
            provided_key.encode("utf-8"), _ADMIN_KEY.encode("utf-8")
        ):
            return jsonify({"error": "Unauthorized"}), 401
        return await f(*args, **kwargs)

    return decorated


def register_admin_routes(app: Quart) -> None:
    """Register admin API routes on the Quart app.

    Args:
        app: Quart application instance
    """

    @app.route("/admin/conversations", methods=["GET"])
    @_require_admin_key
    async def get_conversations():
        """Get conversation summaries for a user."""
        email = request.args.get("email")
        if not email:
            return jsonify({"error": "email query parameter is required"}), 400

        summaries = get_conversation_summaries_by_email(email)
        return jsonify(summaries), 200

    @app.route("/admin/conversations/<path:thread_id>/messages", methods=["GET"])
    @_require_admin_key
    async def get_conversation_messages(thread_id: str):
        """Get full message history for a conversation thread."""
        messages = get_messages_from_checkpoint(thread_id)

        # Derive user_email from thread_id (format: "user@example.com:c742739921c2")
        user_email = thread_id.split(":")[0] if ":" in thread_id else ""

        return jsonify(
            {
                "thread_id": thread_id,
                "user_email": user_email,
                "messages": messages,
            }
        ), 200
