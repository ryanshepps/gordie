"""Email webhook route handler."""

import threading
import time

from quart import jsonify, request

from module.logger import get_logger
from module.metrics import http_request_duration_seconds, webhook_requests_total


def register_email_routes(app):
    """
    Register email-related routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/email/webhook", methods=["POST"])
    async def email_webhook():
        """Handle incoming emails from Mailgun webhook."""
        start_time = time.time()
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
        references = form.get("References")
        message_id = form.get("Message-Id")

        # Validate required fields
        if not all([sender_email, timestamp, token, signature]):
            duration = time.time() - start_time
            webhook_requests_total.labels(webhook_type="email", status="invalid").inc()
            http_request_duration_seconds.labels(method="POST", endpoint="/email/webhook").observe(
                duration
            )

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
            duration = time.time() - start_time
            webhook_requests_total.labels(webhook_type="email", status="expired").inc()
            http_request_duration_seconds.labels(method="POST", endpoint="/email/webhook").observe(
                duration
            )

            logger.error(f"Webhook timestamp too old: {timestamp}")
            return jsonify({"error": "Timestamp too old"}), 403

        if not verify_mailgun_webhook(token, timestamp, signature):
            duration = time.time() - start_time
            webhook_requests_total.labels(webhook_type="email", status="invalid_signature").inc()
            http_request_duration_seconds.labels(method="POST", endpoint="/email/webhook").observe(
                duration
            )

            logger.error(f"Invalid webhook signature from {sender_email}")
            return jsonify({"error": "Invalid signature"}), 403

        # Idempotency: check if we've already processed this Message-Id
        if message_id:
            from sqlalchemy import text as sql_text

            from data.database import get_session

            session = get_session()
            try:
                existing = session.execute(
                    sql_text("SELECT 1 FROM processed_emails WHERE message_id = :message_id"),
                    {"message_id": message_id},
                ).fetchone()

                if existing:
                    logger.info(f"Duplicate email {message_id}, skipping")
                    webhook_requests_total.labels(webhook_type="email", status="duplicate").inc()
                    return jsonify({"status": "duplicate"}), 200

                session.execute(
                    sql_text(
                        "INSERT INTO processed_emails (message_id, sender_email) "
                        "VALUES (:message_id, :sender_email)"
                    ),
                    {"message_id": message_id, "sender_email": sender_email},
                )
                session.commit()
            finally:
                session.close()

        logger.info(
            f"Received email from {sender_email}: {subject}", extra={"user_email": sender_email}
        )
        if in_reply_to:
            logger.info(f"Email is a reply to: {in_reply_to}")

        # Resolve thread_id based on email headers
        from server.thread_manager import resolve_thread

        thread_info = resolve_thread(
            user_email=sender_email,
            in_reply_to=in_reply_to,
            references=references,
            subject=subject,
        )

        logger.info(
            f"Thread resolved: {thread_info.thread_id} "
            f"(new={thread_info.is_new_thread}, subject={thread_info.subject})"
        )

        # Process in background thread
        def process_email():
            try:
                from server.tier_enforcement import build_upgrade_message, check_usage_allowed

                allowed, reason = check_usage_allowed(sender_email, "question")
                if not allowed:
                    upgrade_msg = build_upgrade_message(sender_email, reason, "email")

                    from server.email_formatter import FooterType, format_email
                    from server.email_service import EmailService

                    reply_subject = f"Re: {subject}" if subject else "Gordie"
                    email_content = format_email(
                        content=upgrade_msg, footer_type=FooterType.UNSUBSCRIBE
                    )
                    EmailService().send_email(
                        to_email=sender_email,
                        subject=reply_subject,
                        text_body=email_content.text_body,
                        html_body=email_content.html_body,
                    )
                    logger.info(f"Rate-limited email from {sender_email}, sent upgrade message")
                    return

                from scripts.message_agent import message_agent

                logger.info(f"Processing email from {sender_email}")
                message_agent(
                    message=message_body,
                    thread_id=thread_info.thread_id,
                    channel="email",
                    user_email=sender_email,
                    original_subject=thread_info.subject,
                    original_message=message_body,
                )
                logger.info(f"Agent processing complete for {sender_email}")

            except Exception as e:
                logger.error(f"Error processing email from {sender_email}: {e}", exc_info=True)

        # Start background thread
        thread = threading.Thread(target=process_email, daemon=True)
        thread.start()

        # Record metrics
        duration = time.time() - start_time
        webhook_requests_total.labels(webhook_type="email", status="success").inc()
        http_request_duration_seconds.labels(method="POST", endpoint="/email/webhook").observe(
            duration
        )

        # Return immediately to Mailgun
        return jsonify({"status": "received"}), 200
