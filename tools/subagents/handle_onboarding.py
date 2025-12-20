"""Tool wrapper for the onboarding sub-agent."""

from typing import Annotated, Any, cast

from langchain.tools import InjectedState, tool

from module.logger import get_logger

logger = get_logger(__name__)


@tool
def handle_onboarding(
    request: str,
    user_email: str,
    state: Annotated[dict[str, Any], InjectedState] | None = None,
) -> str:
    """Handle team onboarding and Yahoo Fantasy authentication.

    Use this when the user wants to:
    - Connect their Yahoo Fantasy account
    - Add a new team to track
    - Set up authentication
    - Onboard a team
    - Link their fantasy account

    Args:
        request: The user's onboarding request in natural language
        user_email: The user's email address for authentication

    Returns:
        The onboarding agent's response with instructions or confirmation
    """
    # Import here to avoid circular imports
    from langchain_core.messages import SystemMessage

    from agent.OnboardingAgent import agent as onboarding_agent

    logger.info(f"[handle_onboarding] Processing request for {user_email}: {request[:100]}...")

    # Get persona from state if available
    persona = state.get("persona", "") if state else ""

    # Inject persona and user context as system messages
    system_messages = []

    if persona:
        system_messages.append(SystemMessage(content=persona))

    user_context_msg = SystemMessage(
        content=f"Current user email for this session: {user_email}"
    )
    system_messages.append(user_context_msg)

    # Build input state with required messages field
    input_state = {
        "messages": [*system_messages, {"role": "user", "content": request}],
    }

    result = onboarding_agent.invoke(cast(Any, input_state))

    # Extract the last AI message content
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        response = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        logger.info(f"[handle_onboarding] Response: {response[:200]}...")
        return response

    return "I encountered an issue processing your onboarding request. Please try again."
