import argparse

# Initialize tracing BEFORE any application imports so that
# Logfire's auto-tracing can rewrite modules at import time.
from module.tracing import init

init()

from langchain_core.runnables import RunnableConfig  # noqa: E402

from agent.agent_state import AgentState  # noqa: E402
from agent.graph_builder import agent  # noqa: E402
from module.logger import get_logger  # noqa: E402
from module.tracing import create_span  # noqa: E402

logger = get_logger(__name__)


def _resolve_user_email(
    channel: str,
    user_email: str | None,
    phone_number: str | None,
    thread_id: str,
) -> str | None:
    """Resolve user email based on channel and available identifiers.

    Args:
        channel: Channel type ("email", "sms", or "web")
        user_email: Provided user email (if any)
        phone_number: Provided phone number (if any)
        thread_id: Thread ID (for web channel lookups)

    Returns:
        Resolved email address or None if not resolvable
    """
    if user_email:
        return user_email

    if channel == "sms" and phone_number:
        from data.user_repository import UserRepository

        repo = UserRepository()
        try:
            user = repo.get_user_by_phone(phone_number)
            if user:
                return str(user[0])  # email is the first column
        finally:
            repo.close()
        return None

    if channel == "web":
        from data.web_thread_repository import WebThreadRepository

        repo = WebThreadRepository()
        try:
            web_thread = repo.get_web_thread_by_thread_id(thread_id)
            if web_thread:
                # thread_id format is "email:uuid", extract email
                parts = thread_id.split(":")
                if len(parts) >= 2:
                    return parts[0]
        finally:
            repo.close()

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
) -> str:
    """
    Send a message to the agent graph and continue the conversation.

    Args:
        message: Message content to send to the agent
        thread_id: Conversation thread ID
        channel: Channel type ("email", "sms", or "web")
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

    with create_span("agent.message", {"user.email": email, "thread.id": thread_id}):
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
                "has_rich_content": False,
            }

            # Send message to agent graph
            response = agent.invoke(initial_state, config=config)

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
        from server.thread_manager import resolve_thread

        thread_info = resolve_thread(user_email=args.email)
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
