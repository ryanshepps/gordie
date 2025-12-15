import argparse

from agent.AgentGraph import AgentState
from agent.OnboardingAgent import agent
from data.user_repository import UserRepository
from module.logger import get_logger

logger = get_logger(__name__)


def onboard_user(email: str):
    """Onboard a new user by starting the OnboardingAgent conversation."""
    user_repo = UserRepository()
    if not user_repo.get_user(email):
        logger.info(f"User {email} not found. Creating new user...")
        try:
            user_repo.add_user(email)
            logger.info(f"✓ User {email} created")
        except Exception as e:
            user_repo.close()
            logger.error(f"\n✗ Failed to create new user: {e}")
            raise
    user_repo.close()

    # Invoke OnboardingAgent - it will handle OAuth flow and team selection
    try:
        logger.info(f"\n✓ Starting onboarding agent for {email}...")
        config = {"configurable": {"thread_id": email}}

        # Start the agent conversation
        initial_state: AgentState = {
            "user_email": email,
            "messages": [{"role": "user", "content": f"Hello! My email is {email}"}],
        }

        response = agent.invoke(initial_state, config=config)

        logger.info("\nGordie's Response:")
        if response and "messages" in response:
            for msg in response["messages"]:
                if hasattr(msg, "content"):
                    logger.info(msg.content)

    except Exception as e:
        logger.error(f"\n✗ Failed to start onboarding agent: {e}")
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
