from datetime import datetime

from data.user_repository import UserRepository
from module.logger import get_logger
from server.oauth import initiate_oauth_flow

logger = get_logger(__name__)


def main():
    # Create a random user email with date appended
    email = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"
    user_repo = UserRepository()
    user_repo.add_user(email)
    user_repo.close()

    # Run OAuth flow for the user
    try:
        initiate_oauth_flow(email)
        logger.info(f"✓ OAuth flow completed for {email}")
    except Exception as e:
        logger.error(f"\n✗ OAuth flow failed: {e}")
        raise


if __name__ == "__main__":
    main()
