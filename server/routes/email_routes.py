"""Email webhook route handler."""

import threading

from flask import jsonify, request

from module.logger import get_logger


def register_email_routes(app):
    """
    Register email-related routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/email/webhook", methods=["POST"])
    def email_webhook():
        """Handle incoming emails from Mailgun webhook."""
        logger = get_logger(__name__)

        # Extract webhook data
        sender_email = request.form.get("sender")
        subject = request.form.get("subject", "")
        message_body = request.form.get("stripped-text") or request.form.get("body-plain", "")
        timestamp = request.form.get("timestamp")
        token = request.form.get("token")
        signature = request.form.get("signature")

        # Extract email threading headers
        in_reply_to = request.form.get("In-Reply-To")
        references = request.form.get("References")
        _ = request.form.get("Message-Id")  # Extracted but not currently used

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

        logger.info(f"Received email from {sender_email}: {subject}")
        if in_reply_to:
            logger.info(f"Email is a reply to: {in_reply_to}")

        # Resolve thread_id based on email headers
        from server.email_thread_manager import resolve_thread

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
                from scripts.message_agent import message_agent

                # Process through agent - email sending is handled by the agent graph's email_node
                logger.info(f"Processing email from {sender_email}")
                message_agent(
                    email=sender_email,
                    message=message_body,
                    thread_id=thread_info.thread_id,
                    original_subject=thread_info.subject,
                    original_message=message_body,
                )
                logger.info(f"Agent processing complete for {sender_email}")

            except Exception as e:
                logger.error(f"Error processing email from {sender_email}: {e}", exc_info=True)

        # Start background thread
        thread = threading.Thread(target=process_email, daemon=True)
        thread.start()

        # Return immediately to Mailgun
        return jsonify({"status": "received"}), 200
