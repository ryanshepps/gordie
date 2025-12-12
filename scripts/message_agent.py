import argparse
from agent.OnboardingAgent import agent
from module.logger import get_logger


logger = get_logger(__name__)


def message_agent(email: str, message: str):
    """Send a message to the onboarding agent and continue the conversation."""
    try:
        config = {"configurable": {"thread_id": email}}

        # Send message to agent
        response = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config
        )

        logger.info("\nGordie's Response:\n")
        if response and "messages" in response:
            for msg in response["messages"]:
                if hasattr(msg, "content"):
                    logger.info(msg.content)

    except Exception as e:
        logger.error(f"\n✗ Failed to send message to agent: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Send a message to the onboarding agent")
    parser.add_argument("email", type=str, help="User's email address (thread ID)")
    parser.add_argument("message", type=str, help="Message to send to the agent")

    args = parser.parse_args()
    try:
        message_agent(args.email, args.message)
    except Exception as e:
        logger.error(f"\n✗ Failed to message agent: {e}")
        raise


if __name__ == "__main__":
    main()
