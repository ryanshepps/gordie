"""SMS webhook route handler."""

import threading
import time
from collections import defaultdict

from quart import jsonify, request
from sqlalchemy import text

from data.database import get_session
from data.pending_user_repository import PendingUserRepository
from data.user_repository import UserRepository
from module.logger import get_logger
from module.metrics import (
    http_request_duration_seconds,
    sms_rate_limited_total,
    sms_webhook_requests_total,
)
from server.sms_service import SmsService
from server.thread_manager import resolve_sms_thread
from server.webhook_verification import verify_sinch_webhook

# In-memory rate limiting: phone_number -> list of timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 60

OPT_OUT_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}
OPT_IN_KEYWORDS = {"start"}


def _is_rate_limited(phone_number: str) -> bool:
    """Check if a phone number has exceeded the rate limit."""
    now = time.time()
    timestamps = _rate_limit_store[phone_number]
    # Prune old timestamps
    _rate_limit_store[phone_number] = [
        ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW_SECONDS
    ]
    return len(_rate_limit_store[phone_number]) >= RATE_LIMIT_MAX


def _record_request(phone_number: str) -> None:
    """Record a request timestamp for rate limiting."""
    _rate_limit_store[phone_number].append(time.time())


def register_sms_routes(app):
    """Register SMS-related routes on the Quart app."""

    @app.route("/sms/webhook", methods=["POST"])
    async def sms_webhook():
        """Handle incoming SMS from Sinch webhook."""
        start_time = time.time()
        logger = get_logger(__name__, log_file="server.log")

        raw_body_data = await request.get_data()
        assert isinstance(raw_body_data, bytes)
        raw_body: bytes = raw_body_data
        data = await request.get_json()

        if not data:
            sms_webhook_requests_total.labels(status="invalid").inc()
            logger.error("Empty or invalid JSON body")
            return jsonify({"error": "Invalid request"}), 400

        phone_number = data.get("from")
        message_body = data.get("body", "")
        sinch_message_id = data.get("id")

        if not phone_number or not sinch_message_id:
            sms_webhook_requests_total.labels(status="invalid").inc()
            logger.error("Missing required SMS webhook fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Verify HMAC signature
        signature = request.headers.get("x-sinch-webhook-signature", "")
        if not verify_sinch_webhook(raw_body, signature):
            duration = time.time() - start_time
            sms_webhook_requests_total.labels(status="invalid_signature").inc()
            http_request_duration_seconds.labels(method="POST", endpoint="/sms/webhook").observe(
                duration
            )
            logger.error(f"Invalid Sinch webhook signature from {phone_number}")
            return jsonify({"error": "Invalid signature"}), 403

        # Idempotency: check if we've already processed this message
        session = get_session()
        try:
            existing = session.execute(
                text("SELECT 1 FROM processed_sms WHERE message_id = :message_id"),
                {"message_id": sinch_message_id},
            ).fetchone()

            if existing:
                logger.info(f"Duplicate SMS {sinch_message_id}, skipping")
                sms_webhook_requests_total.labels(status="duplicate").inc()
                return jsonify({"status": "duplicate"}), 200

            session.execute(
                text(
                    "INSERT INTO processed_sms (message_id, phone_number) "
                    "VALUES (:message_id, :phone_number)"
                ),
                {"message_id": sinch_message_id, "phone_number": phone_number},
            )
            session.commit()
        finally:
            session.close()

        # Rate limiting
        if _is_rate_limited(phone_number):
            sms_webhook_requests_total.labels(status="rate_limited").inc()
            sms_rate_limited_total.labels(phone_number=phone_number).inc()
            logger.warning(f"Rate limited SMS from {phone_number}")
            return jsonify({"status": "rate_limited"}), 200

        _record_request(phone_number)

        # Handle opt-out/opt-in keywords
        normalized = message_body.strip().lower()
        if normalized in OPT_OUT_KEYWORDS:
            repo = UserRepository()
            try:
                repo.set_sms_opt_out(phone_number, opted_out=True)
            finally:
                repo.close()

            try:
                sms_service = SmsService()
                sms_service.send_sms(
                    phone_number,
                    "You've been unsubscribed from Gordie SMS. Text START to re-subscribe.",
                )
            except Exception as e:
                logger.error(f"Failed to send opt-out confirmation: {e}")

            sms_webhook_requests_total.labels(status="opt_out").inc()
            logger.info(f"SMS opt-out from {phone_number}")
            return jsonify({"status": "opt_out"}), 200

        if normalized in OPT_IN_KEYWORDS:
            repo = UserRepository()
            try:
                repo.set_sms_opt_out(phone_number, opted_out=False)
            finally:
                repo.close()

            try:
                sms_service = SmsService()
                sms_service.send_sms(
                    phone_number,
                    "You've been re-subscribed to Gordie SMS. Text STOP to unsubscribe.",
                )
            except Exception as e:
                logger.error(f"Failed to send opt-in confirmation: {e}")

            sms_webhook_requests_total.labels(status="opt_in").inc()
            logger.info(f"SMS opt-in from {phone_number}")
            return jsonify({"status": "opt_in"}), 200

        # Check opt-out status for non-keyword messages
        user_repo = UserRepository()
        try:
            if user_repo.is_sms_opted_out(phone_number):
                sms_webhook_requests_total.labels(status="opted_out").inc()
                logger.info(f"SMS from opted-out user {phone_number}, skipping")
                return jsonify({"status": "opted_out"}), 200

            # User lookup: registered user -> pending user -> create pending user
            user = user_repo.get_user_by_phone(phone_number)
        finally:
            user_repo.close()

        user_email: str | None = None
        if user:
            user_email = str(user[0])
        else:
            pending_repo = PendingUserRepository()
            try:
                pending_user = pending_repo.get_pending_user_by_phone(phone_number)
                if not pending_user:
                    pending_repo.add_pending_user(phone_number=phone_number)
                    logger.info(f"Created pending user for phone {phone_number}")
            finally:
                pending_repo.close()

        logger.info(f"Received SMS from {phone_number}: {message_body[:50]}")

        # Resolve thread
        thread_info = resolve_sms_thread(phone_number, message_body)

        logger.info(
            f"SMS thread resolved: {thread_info.thread_id} (new={thread_info.is_new_thread})"
        )

        # Process in background thread
        def process_sms():
            try:
                from scripts.message_agent import message_agent

                message_agent(
                    message=message_body,
                    thread_id=thread_info.thread_id,
                    channel="sms",
                    user_email=user_email,
                    phone_number=phone_number,
                )
                logger.info(f"Agent processing complete for SMS from {phone_number}")
            except Exception as e:
                logger.error(f"Error processing SMS from {phone_number}: {e}", exc_info=True)

        thread = threading.Thread(target=process_sms, daemon=True)
        thread.start()

        duration = time.time() - start_time
        sms_webhook_requests_total.labels(status="success").inc()
        http_request_duration_seconds.labels(method="POST", endpoint="/sms/webhook").observe(
            duration
        )

        return jsonify({"status": "received"}), 200
