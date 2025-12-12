from datetime import datetime
from scripts.add_user import add_user
from server.OAuthCallbackServer import initiate_oauth_flow
from module.logger import get_logger

logger = get_logger(__name__)

def main():
    # Create a random user email with date appended
    email = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
    add_user(email)

    # Run OAuth flow for the user
    try:
        initiate_oauth_flow(email)
        logger.info(f"✓ OAuth flow completed for {email}")
    except Exception as e:
        logger.error(f"\n✗ OAuth flow failed: {e}")
        raise

if __name__ == "__main__":
    main()
