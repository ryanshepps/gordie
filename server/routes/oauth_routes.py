"""OAuth callback route handler."""

import os
import threading
from html import escape

from quart import request

from module.logger import get_logger

logger = get_logger(__name__)


def register_oauth_routes(app):
    """Register OAuth-related routes on the Flask app.

    Args:
        app: Flask application instance
    """

    @app.route("/callback")
    async def callback():
        """Handle OAuth callback from Yahoo.

        The callback is fully self-contained: it exchanges the auth code for
        tokens, saves them, cleans up the pending_oauth row, and spawns a
        background thread to re-invoke the agent so the user's conversation
        continues automatically.
        """
        code = request.args.get("code")
        error = request.args.get("error")
        error_description = request.args.get("error_description")
        state = request.args.get("state")  # pending_oauth UUID

        if error:
            logger.error(f"OAuth error: {error} — {error_description}")
            return (
                _error_html(
                    "Authentication Error",
                    f"{escape(error)}: {escape(error_description or 'No description')}",
                ),
                400,
            )

        if not code or not state:
            return _error_html("Invalid Request", "Missing authorization code or state parameter."), 400

        # Look up pending OAuth record
        from data.pending_oauth_repository import PendingOAuthRepository

        repo = PendingOAuthRepository()
        try:
            record = repo.get(state)
            if not record:
                logger.error(f"No pending_oauth record for state={state}")
                return (
                    _error_html(
                        "Authentication Link Expired",
                        "This OAuth link is no longer valid. It may have already been used or expired. "
                        "Please request a new authentication link.",
                    ),
                    400,
                )

            # Unpack record columns
            # (id, nonce, user_email, phone_number, thread_id, channel, created_at)
            _, nonce, user_email, phone_number, thread_id, channel, _ = record

            # Exchange code for tokens
            client_id = os.getenv("YAHOO_CLIENT_ID")
            client_secret = os.getenv("YAHOO_CLIENT_SECRET")
            oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")

            if not client_id or not client_secret:
                logger.error("YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET must be set")
                return _error_html("Configuration Error", "OAuth is not properly configured."), 500

            callback_url = f"{oauth_base_url.rstrip('/')}/callback"

            from server.oauth import exchange_code, get_yahoo_email, validate_nonce

            token_data = exchange_code(code, client_id, client_secret, callback_url, nonce)
            logger.info(f"Access tokens received for state={state}")

            # Validate nonce from id_token if present
            if "id_token" in token_data:
                validate_nonce(token_data["id_token"], nonce)

            # Get Yahoo email
            yahoo_email = get_yahoo_email(token_data["access_token"])
            if not yahoo_email:
                logger.error(f"Could not retrieve Yahoo email for state={state}")
                return _error_html("Authentication Error", "Could not retrieve your Yahoo email."), 500

            # Account linking for SMS cold-start: phone_number set, user_email is None
            if phone_number and not user_email:
                from data.pending_user_repository import PendingUserRepository
                from data.user_repository import UserRepository

                user_repo = UserRepository()
                try:
                    existing_user = user_repo.get_user(yahoo_email)
                    if existing_user:
                        user_repo.add_phone_to_user(yahoo_email, phone_number)
                        logger.info(f"Linked phone {phone_number} to existing user {yahoo_email}")
                    else:
                        user_repo.add_user_with_phone(yahoo_email, phone_number)
                        logger.info(f"Created new user {yahoo_email} with phone {phone_number}")
                finally:
                    user_repo.close()

                pending_user_repo = PendingUserRepository()
                try:
                    pending = pending_user_repo.get_pending_user_by_phone(phone_number)
                    if pending:
                        pending_user_repo.delete_pending_user(str(pending[0]))
                        logger.info(f"Deleted pending_user for phone {phone_number}")
                finally:
                    pending_user_repo.close()

                user_email = yahoo_email

            # Determine user identifier for saving tokens
            identifier = user_email or phone_number
            if not identifier:
                logger.error(f"No user identifier in pending_oauth record state={state}")
                return _error_html("Authentication Error", "No user identifier found."), 500

            # Save tokens
            from data.yahoo_token_repository import save_tokens

            save_tokens(identifier, yahoo_email, token_data)
            logger.info(f"Tokens saved for user={identifier}")

            # Delete the pending_oauth record
            repo.delete_by_id(state)
            logger.info(f"Deleted pending_oauth record state={state}")

            # Spawn background thread to re-invoke agent
            def resume_agent():
                try:
                    from scripts.message_agent import message_agent

                    message_agent(
                        message="I've completed the OAuth authentication!",
                        thread_id=thread_id,
                        channel=channel,
                        user_email=user_email,
                        phone_number=phone_number,
                        original_subject="Yahoo Fantasy Authentication",
                    )
                    logger.info(f"Agent resumed for user={identifier} thread={thread_id}")
                except Exception as e:
                    logger.error(f"Failed to resume agent after OAuth: {e}", exc_info=True)

            threading.Thread(target=resume_agent, daemon=True).start()

            return _success_html()

        except Exception as e:
            logger.error(f"OAuth callback error: {e}", exc_info=True)
            return _error_html("Authentication Error", "An unexpected error occurred."), 500
        finally:
            repo.close()


def _success_html() -> str:
    return """
    <html>
        <body>
            <h1>Authentication Successful!</h1>
            <p>You can close this window and return to your conversation.</p>
        </body>
    </html>
    """


def _error_html(title: str, message: str) -> str:
    return f"""
    <html>
        <body>
            <h1>{title}</h1>
            <p>{message}</p>
        </body>
    </html>
    """
