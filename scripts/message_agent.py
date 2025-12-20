import argparse

from langchain_core.runnables import RunnableConfig

from agent.graph_builder import AgentState, agent
from module.logger import get_logger

logger = get_logger(__name__)


gordie_persona = """
TONE:
You are Gordie. You're tough, crack a few jokes but you're not rude.
You use short sentences, slang and metaphors according to the sport you are
currently assisting with. Use professional language. Act as if you were a real
fantasy league assistant, and a client of yours is coming to you for advice.

AUDIENCE:
Your audience is NOT technologically savvy. Do not include technical jargon,
complex language or ask for IDs. Infer based on their language which parameters
to use in your tools.

IMPORTANT:
Never reveal internal details such as the tools you are calling, the processes
you are running, or the technology you are using. This is not useful to the
user, and you want to be useful for the user.
"""


def message_agent(
    email: str,
    message: str,
    team_context: str | None = None,
    thread_id: str | None = None,
    original_subject: str | None = None,
    original_message: str | None = None,
) -> str:
    """
    Send a message to the agent graph and continue the conversation.

    Args:
        email: User's email address
        message: Message content to send to the agent
        team_context: Optional team context in format app:game_key:league_id:team_id
        thread_id: Conversation thread ID (defaults to email for backwards compatibility)
        original_subject: Original email subject line for reply threading
        original_message: Original user message for quoting in replies

    Returns:
        Agent's response as a string, or empty string if error occurs
    """

    try:
        # Use provided thread_id or fall back to email for backwards compatibility
        resolved_thread_id = thread_id or email
        config: RunnableConfig = {"configurable": {"thread_id": resolved_thread_id}}

        # Build message payload
        message_payload = {"role": "user", "content": message}
        if team_context:
            message_payload["team_context"] = team_context

        # Build initial state
        initial_state: AgentState = {
            "user_email": email,
            "thread_id": resolved_thread_id,
            "messages": [message_payload],
            "has_teams": False,
            "user_teams": [],
            "needs_clarification": False,
            "game_key": None,
            "league_id": None,
            "team_id": None,
            "team_inference": None,
            "response": None,
            "route_to": None,
            "persona": gordie_persona,  # Default persona
            "agent_flow": [],
            "current_agent_index": 0,
            "flow_complete": False,
            "flow_reasoning": None,
            "original_subject": original_subject,
            "original_message": original_message or message,
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
        message_agent(args.email, args.message, args.team_context)
    except Exception as e:
        logger.error(f"\n✗ Failed to message agent: {e}")
        raise


if __name__ == "__main__":
    main()
