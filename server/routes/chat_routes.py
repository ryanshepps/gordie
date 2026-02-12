"""Chat API routes for web-based conversation streaming."""

import json
import time
from collections import defaultdict

from langchain_core.messages import AIMessageChunk
from langchain_core.runnables import RunnableConfig
from quart import Quart, Response, jsonify, request

from agent.agent_state import AgentState
from agent.async_graph_builder import get_async_agent
from agent.checkpoint_reader import get_messages_from_checkpoint
from data.web_thread_repository import WebThreadRepository
from module.logger import get_logger
from module.metrics import web_chat_requests_total

logger = get_logger(__name__, log_file="server.log")

# In-memory rate limiting: IP -> list of timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW_SECONDS = 60


def _is_rate_limited(ip: str) -> bool:
    """Check if an IP has exceeded the rate limit."""
    now = time.time()
    timestamps = _rate_limit_store[ip]
    _rate_limit_store[ip] = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW_SECONDS]
    return len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX


def _record_request(ip: str) -> None:
    """Record a request timestamp for rate limiting."""
    _rate_limit_store[ip].append(time.time())


def _lookup_thread_id(web_thread_id: str) -> str | None:
    """Look up the conversation thread_id for a web_thread_id."""
    repo = WebThreadRepository()
    try:
        record = repo.get_web_thread(web_thread_id)
        if record:
            return str(record[1])  # thread_id is second column
    finally:
        repo.close()
    return None


def _resolve_user_email_from_thread(thread_id: str) -> str | None:
    """Extract user email from thread_id format (email:uuid or sms:phone:uuid)."""
    parts = thread_id.split(":")
    # Email threads: "user@example.com:uuid"
    if len(parts) >= 2 and "@" in parts[0]:
        return parts[0]
    # SMS threads: "sms:phone:uuid" — no email directly available
    return None


def register_chat_routes(app: Quart) -> None:
    """Register chat API routes on the Quart app."""

    @app.route("/api/chat", methods=["POST"])
    async def chat_stream():
        """Stream an agent response via SSE."""
        web_chat_requests_total.labels(status="received").inc()

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        if _is_rate_limited(client_ip):
            web_chat_requests_total.labels(status="rate_limited").inc()
            return jsonify({"error": "Rate limit exceeded"}), 429

        data = await request.get_json()
        if not data:
            web_chat_requests_total.labels(status="error").inc()
            return jsonify({"error": "Invalid request body"}), 400

        web_thread_id = data.get("web_thread_id")
        message = data.get("message", "").strip()

        if not web_thread_id or not message:
            web_chat_requests_total.labels(status="error").inc()
            return jsonify({"error": "web_thread_id and message are required"}), 400

        thread_id = _lookup_thread_id(web_thread_id)
        if not thread_id:
            web_chat_requests_total.labels(status="error").inc()
            return jsonify({"error": "Thread not found"}), 404

        _record_request(client_ip)

        user_email = _resolve_user_email_from_thread(thread_id)

        async def generate():
            try:
                agent = await get_async_agent()
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

                initial_state: AgentState = {
                    "user_email": user_email or "",
                    "thread_id": thread_id,
                    "channel": "web",
                    "messages": [{"role": "user", "content": message}],
                    "user_teams": [],
                    "league_id": None,
                    "team_id": None,
                    "response": None,
                    "route_to": None,
                    "agent_flow": [],
                    "current_agent_index": 0,
                    "flow_complete": False,
                    "flow_reasoning": None,
                    "original_subject": None,
                    "original_message": message,
                    "has_rich_content": False,
                }

                async for event in agent.astream(
                    initial_state, config=config, stream_mode="messages"
                ):
                    # astream with stream_mode="messages" yields (message, metadata) tuples
                    msg, _metadata = event
                    if isinstance(msg, AIMessageChunk) and msg.content:
                        payload = json.dumps({"token": msg.content})
                        yield f"event: token\ndata: {payload}\n\n"

                yield "event: done\ndata: {}\n\n"
                web_chat_requests_total.labels(status="success").inc()

            except Exception as e:
                logger.error(f"Chat stream error for thread {thread_id}: {e}", exc_info=True)
                payload = json.dumps({"error": "An error occurred processing your message"})
                yield f"event: error\ndata: {payload}\n\n"
                web_chat_requests_total.labels(status="error").inc()

        return Response(
            generate(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/api/chat/<web_thread_id>/history", methods=["GET"])
    async def chat_history(web_thread_id: str):
        """Get conversation history for a web thread."""
        thread_id = _lookup_thread_id(web_thread_id)
        if not thread_id:
            return jsonify({"error": "Thread not found"}), 404

        messages = get_messages_from_checkpoint(thread_id)
        return jsonify({"thread_id": thread_id, "messages": messages}), 200
