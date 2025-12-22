"""OAuth callback route handler."""

from flask import request

from module.logger import get_logger


def register_oauth_routes(app, server):
    """
    Register OAuth-related routes on the Flask app.

    Args:
        app: Flask application instance
        server: Server instance for storing auth state
    """

    @app.route("/callback")
    def callback():
        """Handle OAuth callback from Yahoo."""
        logger = get_logger(__name__)

        # Check for authorization code
        code = request.args.get("code")
        error = request.args.get("error")
        error_description = request.args.get("error_description")
        user_email = request.args.get("state")  # user_email passed via state parameter

        if error:
            server.auth_error = error
            logger.error(f"OAuth Error: {error}")
            if error_description:
                logger.error(f"Error Description: {error_description}")
            server.code_received.set()
            return (
                f"""
            <html>
                <body>
                    <h1>Authentication Error</h1>
                    <p>{error}: {error_description or "No description"}</p>
                </body>
            </html>
            """,
                400,
            )

        if code:
            # Prevent duplicate callbacks (browser double-requests, refreshes, etc.)
            if server.auth_code == code:
                logger.warning("Duplicate callback detected, ignoring")
                return """
                <html>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You can close this window and return to your conversation.</p>
                    </body>
                </html>
                """

            # Validate that we have a stored nonce for this user before accepting the callback
            # This prevents infinite loops when old/stale OAuth links are clicked
            if not user_email:
                logger.error("No user email (state) in callback")
                return (
                    """
                <html>
                    <body>
                        <h1>Authentication Error</h1>
                        <p>Invalid OAuth callback: missing user information.</p>
                        <p>Please request a new authentication link.</p>
                    </body>
                </html>
                """,
                    400,
                )

            from server.oauth_nonce import get_oauth_nonce

            nonce = get_oauth_nonce(user_email)
            if not nonce:
                logger.error(f"No stored nonce found for user: {user_email}")
                return (
                    """
                <html>
                    <body>
                        <h1>Authentication Link Expired</h1>
                        <p>This OAuth link is no longer valid.
                           It may have already been used or expired.</p>
                        <p>Please request a new authentication link.</p>
                    </body>
                </html>
                """,
                    400,
                )

            server.auth_code = code
            server.user_email = user_email
            server.code_received.set()
            return """
            <html>
                <body>
                    <h1>Authentication Successful!</h1>
                    <p>You can close this window and return to your conversation.</p>
                </body>
            </html>
            """

        return (
            """
        <html>
            <body>
                <h1>Invalid Request</h1>
                <p>No authorization code received.</p>
            </body>
        </html>
        """,
            400,
        )
