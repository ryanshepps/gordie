import argparse
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from agent.agent_state import AgentState
from agent.graph_builder import agent
from data.conversation_repository import ConversationRepository
from data.models import Medium
from module.logger import get_logger

logger = get_logger(__name__)


def message_agent(
    message: str,
    thread_id: str,
    channel: Medium,
    user_id: str,
    external_id: str,
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
        channel: Channel type
        user_id: Canonical user UUID
        external_id: Medium-native identifier for this conversation
        team_context: Optional team context in format app:game_key:league_id:team_id
        original_subject: Original email subject line for reply threading
        original_message: Original user message for quoting in replies

    Returns:
        Agent's response as a string, or empty string if error occurs
    """
    try:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        message_payload = {"role": "user", "content": message}
        if team_context:
            message_payload["team_context"] = team_context

        initial_state: AgentState = {
            "user_id": user_id,
            "external_id": external_id,
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

        response_text = ""
        if response and response.get("response"):
            response_text = response["response"]
            logger.info(response_text)
        elif response and "messages" in response:
            response_parts = []
            new_messages = response["messages"][len(initial_state["messages"]) :]
            for msg in new_messages:
                if hasattr(msg, "content") and hasattr(msg, "type") and msg.type != "human":
                    response_parts.append(msg.content)
                    logger.info(msg.content)
            response_text = "\n".join(response_parts)

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


def main() -> None:
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
            channel=Medium.EMAIL,
            user_id=str(user_id),
            external_id=args.email,
            team_context=args.team_context,
        )
    except Exception as e:
        logger.error(f"\n✗ Failed to message agent: {e}")
        raise


if __name__ == "__main__":
    main()
