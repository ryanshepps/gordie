"""Signup route handler for website signups."""

import re
import threading

from flask import jsonify, request

from module.logger import get_logger

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def register_signup_routes(app):
    """
    Register signup-related routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/api/signup", methods=["POST"])
    def signup():
        """Handle website signup requests."""
        logger = get_logger(__name__, log_file="server.log")

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid request body."}), 400

        email = (data.get("email") or "").strip().lower()
        if not email or not EMAIL_REGEX.match(email):
            return jsonify({"error": "Please provide a valid email address."}), 400

        logger.info(f"Website signup from {email}")

        from server.email_thread_manager import resolve_thread

        thread_info = resolve_thread(user_email=email, subject="Website Signup")

        def process_signup():
            try:
                from scripts.message_agent import message_agent

                message_agent(
                    email=email,
                    message="Hi! I just signed up on the website. I'd like to get started with Gordie.",
                    thread_id=thread_info.thread_id,
                    original_subject="Welcome to Gordie",
                )
                logger.info(f"Signup agent processing complete for {email}")
            except Exception as e:
                logger.error(f"Error processing signup for {email}: {e}", exc_info=True)

        thread = threading.Thread(target=process_signup, daemon=True)
        thread.start()

        return jsonify({"success": True}), 200
