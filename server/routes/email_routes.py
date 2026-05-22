"""Email webhook route handler."""

import threading
from uuid import UUID

from quart import jsonify, request

from module.logger import get_logger


def register_email_routes(app):
    """
    Register email-related routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/email/webhook", methods=["POST"])
    async def email_webhook():
        """Handle incoming emails from Mailgun webhook."""
        logger = get_logger(__name__, log_file="server.log")

        # Extract webhook data
        form = await request.form
        sender_email = form.get("sender")
        subject = form.get("subject", "")
        message_body = form.get("stripped-text") or form.get("body-plain", "")
        timestamp = form.get("timestamp")
        token = form.get("token")
        signature = form.get("signature")

        # Extract email threading headers
        in_reply_to = form.get("In-Reply-To")
        message_id = form.get("Message-Id")

        # Validate required fields
        if not all([sender_email, timestamp, token, signature]):
            logger.error("Missing required webhook fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Type assertions - we've validated these are not None above
        assert sender_email is not None
        assert timestamp is not None
        assert token is not None
        assert signature is not None

        # Verify signature and timestamp
        from server.webhook_verification import is_timestamp_fresh, verify_mailgun_webhook

        if not is_timestamp_fresh(timestamp):
            logger.error(f"Webhook timestamp too old: {timestamp}")
            return jsonify({"error": "Timestamp too old"}), 403

        if not verify_mailgun_webhook(token, timestamp, signature):
            logger.error(f"Invalid webhook signature from {sender_email}")
            return jsonify({"error": "Invalid signature"}), 403

        # Idempotency: check if we've already processed this Message-Id
        if message_id:
            from data.models import Medium
            from data.processed_inbound_message_repository import (
                ProcessedInboundMessageRepository,
            )

            processed_repo = ProcessedInboundMessageRepository()
            try:
                if not processed_repo.claim(Medium.EMAIL, str(message_id), str(sender_email)):
                    logger.info(f"Duplicate email {message_id}, skipping")
                    return jsonify({"status": "duplicate"}), 200
            finally:
                processed_repo.close()

        logger.info(
            f"Received email from {sender_email}: {subject}", extra={"user_email": sender_email}
        )
        if in_reply_to:
            logger.info(f"Email is a reply to: {in_reply_to}")

        # Resolve thread_id based on email headers
        from data.models import Medium
        from data.thread_repository import ThreadRepository
        from data.user_repository import UserRepository

        user_repo = UserRepository()
        try:
            user = user_repo.get_by_identity(Medium.EMAIL, sender_email)
            user_id = (
                UUID(str(user[0]))
                if user
                else user_repo.create_with_identity(Medium.EMAIL, sender_email, sender_email)
            )
        finally:
            user_repo.close()

        thread_repo = ThreadRepository()
        try:
            thread_info = thread_repo.resolve(user_id, Medium.EMAIL)
        finally:
            thread_repo.close()

        logger.info(
            f"Thread resolved: {thread_info.thread_id} "
            f"(new={thread_info.is_new_thread}, subject={subject})"
        )

        # Process in background thread
        def process_email():
            try:
                from billing import get_gateway

                gateway = get_gateway()
                billing_ctx = None
                allowed, reason = gateway.check_question_allowed(sender_email, message_body)
                if not allowed:
                    billing_ctx = gateway.build_billing_context(sender_email, reason, Medium.EMAIL)

                from scripts.message_agent import message_agent

                logger.info(f"Processing email from {sender_email}")
                message_agent(
                    message=message_body,
                    thread_id=thread_info.thread_id,
                    channel=Medium.EMAIL,
                    user_id=str(user_id),
                    external_id=sender_email,
                    original_subject=subject,
                    original_message=message_body,
                    billing_context=billing_ctx,
                )
                logger.info(f"Agent processing complete for {sender_email}")

            except Exception as e:
                logger.error(f"Error processing email from {sender_email}: {e}", exc_info=True)

        # Start background thread
        thread = threading.Thread(target=process_email, daemon=True)
        thread.start()

        # Return immediately to Mailgun
        return jsonify({"status": "received"}), 200
