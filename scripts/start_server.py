"""Start the server to handle OAuth callbacks and email webhooks."""

import os
import sys
import time

from dotenv import load_dotenv

from module.logger import get_logger
from server.oauth import (
    exchange_code,
    get_yahoo_email,
    notify_onboarding_agent,
    save_tokens,
)
from server.oauth_nonce import delete_oauth_nonce, get_oauth_nonce_and_thread
from server.server import Server

load_dotenv()

logger = get_logger(__name__)


def handle_oauth_callback(server: Server) -> bool:
    """
    Process OAuth callback when received.

    Returns:
        True if callback was processed successfully, False otherwise
    """
    logger.info("Waiting for OAuth callback...")

    try:
        # Wait indefinitely for OAuth callback
        auth_code = server.wait_for_code(timeout=None)

        if not auth_code:
            logger.error("Failed to receive auth code")
            return False

        user_email = server.user_email
        if not user_email:
            logger.error("No user email received in callback")
            return False

        logger.info(f"✓ Authorization code received for user: {user_email}")

        # Retrieve stored nonce and thread_id for this user
        nonce_and_thread = get_oauth_nonce_and_thread(user_email)
        if not nonce_and_thread:
            logger.error(f"No stored nonce/thread found for user: {user_email}")
            return False

        nonce, thread_id = nonce_and_thread

        # Exchange code for tokens
        client_id = os.getenv("YAHOO_CLIENT_ID")
        client_secret = os.getenv("YAHOO_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error("YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET must be set")
            return False

        oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")
        callback_url = server.get_callback_url(oauth_base_url)

        token_data = exchange_code(auth_code, client_id, client_secret, callback_url, nonce)
        logger.info("✓ Access tokens received")

        # Get Yahoo email
        yahoo_email = get_yahoo_email(token_data["access_token"])
        if not yahoo_email:
            logger.error("Could not retrieve Yahoo email")
            return False

        logger.info(f"✓ Yahoo email: {yahoo_email}")
        token_data["yahoo_email"] = yahoo_email

        # Save tokens
        save_tokens(user_email, yahoo_email, token_data)
        logger.info("✓ Tokens saved to database")

        # Delete the used nonce
        delete_oauth_nonce(user_email)

        # Notify the OnboardingAgent with the correct thread_id
        notify_onboarding_agent(user_email, thread_id)
        logger.info("✓ OnboardingAgent notified")

        # Reset for next callback
        server.shutdown()

        return True

    except Exception as e:
        logger.error(f"Error processing OAuth callback: {e}")
        import traceback

        traceback.print_exc()
        # Reset the server state even on error to be ready for next attempt
        server.shutdown()
        return False


def main():
    """Start the server."""
    host = "localhost"
    port = 8000

    logger.info(f"Starting server on {host}:{port}...")
    server = Server(host=host, port=port)

    try:
        server.start()
        logger.info(f"✓ Server running at http://{host}:{port}")
        logger.info("Press Ctrl+C to stop the server")

        # Keep the server running and process callbacks
        while True:
            success = handle_oauth_callback(server)

            # Only continue to next callback if configured for multi-user mode
            # For now, we continue to accept new callbacks for different users
            if success:
                logger.info("Ready to accept another OAuth callback...")
            else:
                logger.warning("Previous callback failed, ready to retry...")

            time.sleep(1)  # Brief pause before accepting next callback

    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
