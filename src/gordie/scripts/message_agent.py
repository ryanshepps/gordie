import argparse
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from gordie.agent.agent_state import AgentState
from gordie.agent.graph_builder import get_agent
from gordie.data.conversation_repository import ConversationRepository
from gordie.data.models import Medium
from gordie.module.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Final agent response and state for caller-owned delivery."""

    response_text: str
    state: AgentState


def message_agent(
    message: str,
    thread_id: str,
    channel: Medium,
    user_id: str,
    external_id: str,
    team_context: str | None = None,
    access_context: str | None = None,
) -> str:
    """Send a message to the agent graph and return the response text."""
    return run_message_agent(
        message=message,
        thread_id=thread_id,
        channel=channel,
        user_id=user_id,
        external_id=external_id,
        team_context=team_context,
        access_context=access_context,
    ).response_text


def run_message_agent(
    message: str,
    thread_id: str,
    channel: Medium,
    user_id: str,
    external_id: str,
    team_context: str | None = None,
    access_context: str | None = None,
) -> AgentRunResult:
    """
    Send a message to the agent graph and continue the conversation.

    Args:
        message: Message content to send to the agent
        thread_id: Conversation thread ID
        channel: Channel type
        user_id: Canonical user UUID
        external_id: Medium-native identifier for this conversation
        team_context: Optional team context in format app:game_key:league_id:team_id

    Returns:
        Agent response text plus final graph state.
    """
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
        "access_context": access_context,
    }

    try:
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

        response = cast(AgentState | None, get_agent().invoke(initial_state, config))
        final_state = response or initial_state

        logger.info("\nGordie's Response:\n")

        response_text = ""
        response_value = final_state.get("response")
        if response_value:
            response_text = str(response_value)
            logger.info(response_text)
        else:
            response_parts = []
            new_messages = final_state["messages"][len(initial_state["messages"]) :]
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

        return AgentRunResult(response_text=response_text.strip(), state=final_state)

    except Exception as e:
        logger.error(f"\n✗ Failed to send message to agent: {e}")
        return AgentRunResult(response_text="", state=initial_state)


def _main() -> None:
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
        from gordie.data.thread_repository import ThreadRepository
        from gordie.data.user_repository import UserRepository

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

        result = run_message_agent(
            message=args.message,
            thread_id=thread_info.thread_id,
            channel=Medium.EMAIL,
            user_id=str(user_id),
            external_id=args.email,
            team_context=args.team_context,
        )
        print(result.response_text)
    except Exception as e:
        logger.error(f"\n✗ Failed to message agent: {e}")
        raise


def main() -> None:
    from dotenv import load_dotenv

    from gordie.integrations.defaults import default_plugins
    from gordie.runtime import Runtime

    load_dotenv()
    runtime = Runtime(default_plugins())
    try:
        with runtime.activate():
            _main()
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
