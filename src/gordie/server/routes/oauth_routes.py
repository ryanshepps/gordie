"""OAuth callback route handler."""

import os
from html import escape
from uuid import UUID

from quart import request

from gordie.module.logger import get_logger
from gordie.server.oauth_config import OAuthConfigurationError, get_oauth_base_url

logger = get_logger(__name__)


def register_oauth_routes(app):
    """Register Yahoo OAuth callback routes on the Quart app.

    Args:
        app: Quart application instance
    """

    @app.route("/callback")
    async def callback():
        """Handle OAuth callback from Yahoo.

        The callback exchanges the authorization code, saves tokens under the
        account identity, and deletes the pending OAuth record.
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
            return _error_html(
                "Invalid Request", "Missing authorization code or state parameter."
            ), 400

        # Look up pending OAuth record
        from gordie.data.pending_oauth_repository import PendingOAuthRepository

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

            _, nonce, medium_value, external_id, _, _ = record
            from gordie.data.models import Medium

            if medium_value != Medium.EMAIL.value:
                return _error_html("Invalid Request", "Unsupported OAuth account identity."), 400

            # Exchange code for tokens
            client_id = os.getenv("YAHOO_CLIENT_ID")
            client_secret = os.getenv("YAHOO_CLIENT_SECRET")

            if not client_id or not client_secret:
                logger.error("YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET must be set")
                return _error_html("Configuration Error", "OAuth is not properly configured."), 500
            try:
                oauth_base_url = get_oauth_base_url()
            except OAuthConfigurationError as exc:
                logger.error(f"{exc}, cannot exchange OAuth callback")
                return _error_html("Configuration Error", "OAuth is not properly configured."), 500

            callback_url = f"{oauth_base_url.rstrip('/')}/callback"

            from gordie.server.oauth import exchange_code, get_yahoo_email, validate_nonce

            token_data = exchange_code(code, client_id, client_secret, callback_url, nonce)
            logger.info(f"Access tokens received for state={state}")

            # Validate nonce from id_token if present
            if "id_token" in token_data:
                validate_nonce(token_data["id_token"], nonce)

            # Get Yahoo email
            yahoo_email = get_yahoo_email(token_data["access_token"])
            if not yahoo_email:
                logger.error(f"Could not retrieve Yahoo email for state={state}")
                return _error_html(
                    "Authentication Error", "Could not retrieve your Yahoo email."
                ), 500

            from gordie.data.user_repository import UserRepository

            user_repo = UserRepository()
            try:
                email_user = user_repo.get_by_identity(Medium.EMAIL, yahoo_email)
                source_user = user_repo.get_by_identity(Medium.EMAIL, str(external_id))
                if email_user:
                    user_id = UUID(str(email_user[0]))
                    if not source_user:
                        user_repo.link_identity(
                            user_id, Medium.EMAIL, str(external_id), str(external_id)
                        )
                    elif UUID(str(source_user[0])) != user_id:
                        user_repo.merge_users(UUID(str(source_user[0])), user_id)
                elif source_user:
                    user_id = UUID(str(source_user[0]))
                    user_repo.link_identity(user_id, Medium.EMAIL, yahoo_email, yahoo_email)
                else:
                    user_id = user_repo.create_with_identity(
                        Medium.EMAIL,
                        yahoo_email,
                        yahoo_email,
                    )
            finally:
                user_repo.close()

            # Save tokens
            from gordie.data.yahoo_token_repository import save_tokens_by_user_id

            save_tokens_by_user_id(str(user_id), yahoo_email, token_data)
            logger.info(f"Tokens saved for user_id={user_id}")

            # Delete the pending_oauth record
            repo.delete_by_id(state)
            logger.info(f"Deleted pending_oauth record state={state}")

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
            <p>You can close this window.</p>
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
