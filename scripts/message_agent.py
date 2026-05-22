import argparse
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from agent.agent_state import AgentState
from agent.graph_builder import agent
from data.conversation_repository import ConversationRepository
from module.logger import get_logger

logger = get_logger(__name__)


def _resolve_user_email(
    channel: str,
    user_email: str | None,
    phone_number: str | None,
    thread_id: str,
) -> str | None:
    """Resolve user email based on channel and available identifiers.

    Args:
        channel: Channel type ("email" or "sms")
        user_email: Provided user email (if any)
        phone_number: Provided phone number (if any)
        thread_id: Thread ID

    Returns:
        Resolved email address or None if not resolvable
    """
    if user_email:
        return user_email

    if channel == "sms" and phone_number:
        from data.models import Medium
        from data.user_repository import UserRepository

        repo = UserRepository()
        try:
            user = repo.get_by_identity(Medium.SMS, phone_number)
            if user:
                return repo.get_identity_external_id(UUID(str(user[0])), Medium.EMAIL)
        finally:
            repo.close()
        return None

    return None


def message_agent(
    message: str,
    thread_id: str,
    channel: str = "email",
    user_email: str | None = None,
    phone_number: str | None = None,
    team_context: str | None = None,
    original_subject: str | None = None,
    original_message: str | None = None,
    billing_context: str | None = None,
) -> str:
    """
    Send a message to the agent graph and continue the conversation.

    Args:
        message: Message content to send to the agent
        thread_id: Conversation thread ID
        channel: Channel type ("email" or "sms")
        user_email: User's email address (required for email channel)
        phone_number: User's phone number (required for sms channel)
        team_context: Optional team context in format app:game_key:league_id:team_id
        original_subject: Original email subject line for reply threading
        original_message: Original user message for quoting in replies

    Returns:
        Agent's response as a string, or empty string if error occurs
    """
    # Resolve user email based on channel
    email = _resolve_user_email(channel, user_email, phone_number, thread_id)
    if not email:
        logger.error(f"Could not resolve user email for channel={channel}")
        return ""

    try:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        # Build message payload
        message_payload = {"role": "user", "content": message}
        if team_context:
            message_payload["team_context"] = team_context

        # Build initial state
        initial_state: AgentState = {
            "user_email": email,
            "thread_id": thread_id,
            "channel": channel,
            "messages": [message_payload],
            "user_teams": [],
            "league_id": None,
            "team_id": None,
            "response": None,
            "route_to": None,
            "agent_flow": [],
            "current_agent_index": 0,
            "flow_complete": False,
            "flow_reasoning": None,
            "original_subject": original_subject,
            "original_message": original_message or message,
            "billing_context": billing_context,
        }

        # Persist user message before invoking graph
        repo = ConversationRepository()
        try:
            repo.add_message(
                thread_id=thread_id,
                checkpoint_id="pending",
                role="human",
                content=message,
                message_type="standard",
            )
            repo.commit()
        finally:
            repo.close()

        response = agent.invoke(initial_state, config)

        logger.info("\nGordie's Response:\n")

        # Extract response text
        response_text = ""

        # Check for direct response first (from clarification node)
        if response and response.get("response"):
            response_text = response["response"]
            logger.info(response_text)
        # Otherwise check messages - only extract NEW agent messages (not entire history)
        elif response and "messages" in response:
            response_parts = []
            # The initial_state contains 1 user message
            # So we want messages AFTER the first one (index 0)
            new_messages = response["messages"][len(initial_state["messages"]) :]
            for msg in new_messages:
                # Only include assistant/AI messages, not user messages
                if hasattr(msg, "content") and hasattr(msg, "type") and msg.type != "human":
                    response_parts.append(msg.content)
                    logger.info(msg.content)
            response_text = "\n".join(response_parts)

        # Persist AI response after graph completes
        if response_text.strip():
            repo = ConversationRepository()
            try:
                repo.add_message(
                    thread_id=thread_id,
                    checkpoint_id="complete",
                    role="ai",
                    content=response_text.strip(),
                    message_type="standard",
                )
                repo.commit()
            finally:
                repo.close()

        return response_text.strip()

    except Exception as e:
        logger.error(f"\n✗ Failed to send message to agent: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(description="Send a message to the onboarding agent")
    parser.add_argument("email", type=str, help="User's email address (thread ID)")
    parser.add_argument("message", type=str, help="Message to send to the agent")
    parser.add_argument(
        "--team-context",
        type=str,
        help="Optional team context in format app:game_key:league_id:team_id",
        default=None,
    )

    args = parser.parse_args()
    try:
        from data.models import Medium
        from data.thread_repository import ThreadRepository
        from data.user_repository import UserRepository

        user_repo = UserRepository()
        try:
            user = user_repo.get_by_identity(Medium.EMAIL, args.email)
            user_id = (
                UUID(str(user[0]))
                if user
                else user_repo.create_with_identity(Medium.EMAIL, args.email, args.email)
            )
        finally:
            user_repo.close()

        thread_repo = ThreadRepository()
        try:
            thread_info = thread_repo.resolve(user_id, Medium.EMAIL)
        finally:
            thread_repo.close()
        message_agent(
            message=args.message,
            thread_id=thread_info.thread_id,
            channel="email",
            user_email=args.email,
            team_context=args.team_context,
        )
    except Exception as e:
        logger.error(f"\n✗ Failed to message agent: {e}")
        raise


if __name__ == "__main__":
    main()
