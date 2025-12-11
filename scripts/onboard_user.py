import argparse
from scripts.add_user import add_user
from scripts.get_user import get_user
from scripts.update_user import update_user
from client.oauth_manager import initiate_oauth_flow
from agent.OnboardingAgent import agent
from module.logger import get_logger


logger = get_logger(__name__)


def onboard_user(email: str):
    """Onboard a new user by adding them to the system and completing OAuth flow."""
    if (not get_user(email)):
        logger.info(f"User {email} not found. Creating new user...")
        try:
            create_new_user(email)
        except Exception as e:
            logger.error(f"\n✗ Failed to create new user: {e}")
            raise

    # Invoke OnboardingAgent
    try:
        logger.info(f"\n✓ Starting onboarding agent for {email}...")
        config = {"configurable": {"thread_id": email}}

        # Start the agent conversation
        response = agent.invoke(
            {"messages": [{"role": "user", "content": f"Hello! My email is {email}"}]},
            config=config
        )

        logger.info("\nGordie's Response:\n")
        if response and "messages" in response:
            for msg in response["messages"]:
                if hasattr(msg, "content"):
                    logger.info(msg.content)

    except Exception as e:
        logger.error(f"\n✗ Failed to start onboarding agent: {e}")
        raise


def create_new_user(email):

    add_user(email)

    # Run OAuth flow for the user first to get Yahoo email
    try:
        token_data = initiate_oauth_flow(email)
        logger.info(f"\n✓ OAuth flow completed for {email}")
        logger.info(f"Access token received: {token_data['access_token'][:20]}...")

        yahoo_email = token_data.get("yahoo_email")
        if yahoo_email:
            logger.info(f"Yahoo email retrieved: {yahoo_email}")

    except Exception as e:
        logger.error(f"\n✗ OAuth flow failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Onboard a new user with OAuth flow")
    parser.add_argument("email", type=str, help="User's email address")

    args = parser.parse_args()
    try:
        onboard_user(args.email)
    except Exception as e:
        logger.error(f"\n✗ Failed to onboard user: {e}")
        raise



if __name__ == "__main__":
    main()
