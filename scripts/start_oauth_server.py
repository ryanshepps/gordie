"""Start the OAuth callback server to handle Yahoo OAuth redirects."""

import os
import sys
import signal
import time
from server.OAuthCallbackServer import (
    OAuthCallbackServer, _exchange_code, _get_yahoo_email, 
    _save_tokens, _notify_onboarding_agent, get_oauth_nonce, delete_oauth_nonce
)
from module.logger import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)


def handle_oauth_callback(server: OAuthCallbackServer) -> bool:
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
        
        # Retrieve stored nonce for this user
        nonce = get_oauth_nonce(user_email)
        if not nonce:
            logger.error(f"No stored nonce found for user: {user_email}")
            return False
        
        # Exchange code for tokens
        client_id = os.getenv("YAHOO_CLIENT_ID")
        client_secret = os.getenv("YAHOO_CLIENT_SECRET")
        oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")
        callback_url = server.get_callback_url(oauth_base_url)
        
        token_data = _exchange_code(auth_code, client_id, client_secret, callback_url, nonce)
        logger.info("✓ Access tokens received")
        
        # Get Yahoo email
        yahoo_email = _get_yahoo_email(token_data["access_token"])
        if not yahoo_email:
            logger.error("Could not retrieve Yahoo email")
            return False
        
        logger.info(f"✓ Yahoo email: {yahoo_email}")
        token_data["yahoo_email"] = yahoo_email
        
        # Save tokens
        _save_tokens(user_email, yahoo_email, token_data)
        logger.info("✓ Tokens saved to database")
        
        # Delete the used nonce
        delete_oauth_nonce(user_email)
        
        # Notify the OnboardingAgent
        _notify_onboarding_agent(user_email)
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
    """Start the OAuth callback server."""
    host = "localhost"
    port = 8000
    
    logger.info(f"Starting OAuth callback server on {host}:{port}...")
    server = OAuthCallbackServer(host=host, port=port)
    
    try:
        server.start()
        logger.info(f"✓ OAuth callback server running at http://{host}:{port}")
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
        logger.info("\nShutting down OAuth callback server...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
