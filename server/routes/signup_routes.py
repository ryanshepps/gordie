"""Signup route handler for website signups."""

import re
import threading

from quart import jsonify, request

from module.logger import get_logger

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_REGEX = re.compile(r"^\+[1-9]\d{9,14}$")


def register_signup_routes(app):
    """Register signup-related routes on the Quart app.

    Args:
        app: Quart application instance
    """

    @app.route("/api/signup", methods=["POST"])
    async def signup():
        """Handle website signup requests.

        Accepts { email?, phone_number? } — at least one required.
        Email path triggers the agent welcome flow via email.
        Phone path sends an OAuth SMS for Yahoo league connection.
        """
        logger = get_logger(__name__, log_file="server.log")

        data = await request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid request body."}), 400

        email = (data.get("email") or "").strip().lower() or None
        phone_number = (data.get("phone_number") or "").strip() or None

        if not email and not phone_number:
            return jsonify({"error": "Please provide an email address or phone number."}), 400

        if email and not EMAIL_REGEX.match(email):
            return jsonify({"error": "Please provide a valid email address."}), 400

        if phone_number and not PHONE_REGEX.match(phone_number):
            return jsonify({"error": "Please provide a valid phone number (e.g. +12025551234)."}), 400

        # Email signup path
        if email:
            logger.info(f"Website signup (email) from {email}")

            from server.thread_manager import resolve_thread

            thread_info = resolve_thread(user_email=email, subject="Website Signup")

            def process_email_signup():
                try:
                    from scripts.message_agent import message_agent

                    message_agent(
                        message="Hi! I just signed up on the website. I'd like to get started with Gordie.",
                        thread_id=thread_info.thread_id,
                        channel="email",
                        user_email=email,
                        original_subject="Welcome to Gordie",
                    )
                    logger.info(f"Signup agent processing complete for {email}")
                except Exception as e:
                    logger.error(f"Error processing signup for {email}: {e}", exc_info=True)

            threading.Thread(target=process_email_signup, daemon=True).start()

        # Phone signup path
        if phone_number:
            logger.info(f"Website signup (phone) from {phone_number}")

            from data.pending_user_repository import PendingUserRepository
            from server.thread_manager import resolve_sms_thread

            pending_repo = PendingUserRepository()
            try:
                pending_user = pending_repo.get_pending_user_by_phone(phone_number)
                if not pending_user:
                    pending_repo.add_pending_user(phone_number=phone_number)
            finally:
                pending_repo.close()

            thread_info = resolve_sms_thread(phone_number, "Website Signup")

            try:
                from server.routes.sms_routes import _generate_cold_start_oauth_link
                from server.sms_service import SmsService

                oauth_url = _generate_cold_start_oauth_link(phone_number, thread_info.thread_id)
                sms_service = SmsService()
                sms_service.send_sms(
                    phone_number,
                    f"Hey, I'm Gordie \u2014 your fantasy hockey guy. "
                    f"Tap here to connect your Yahoo league: {oauth_url}",
                )
                logger.info(f"Sent signup OAuth SMS to {phone_number}")
            except Exception as e:
                logger.error(f"Failed to send signup OAuth SMS to {phone_number}: {e}")
                if not email:
                    return jsonify({"error": "Failed to send verification SMS. Please try again."}), 500

        return jsonify({"success": True}), 200
