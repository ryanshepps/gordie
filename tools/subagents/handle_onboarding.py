"""Tool wrapper for the onboarding sub-agent."""

import json
from typing import Annotated, Any, cast

from langchain.tools import InjectedState, tool
from langchain_core.runnables import RunnableConfig

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
        JSON with 'status', 'message', and optionally 'oauth_url'.
        If oauth_url is present, you MUST include this exact URL in your response to the user.
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

    # Build config with thread_id for conversation isolation
    thread_id = state.get("thread_id", user_email) if state else user_email
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    result = onboarding_agent.invoke(cast(Any, input_state), config)

    # Extract structured response and return as JSON
    structured = result.get("structured_response")
    if structured:
        response_data = {
            "status": "success",
            "message": structured.message,
        }
        if structured.oauth_url:
            response_data["oauth_url"] = structured.oauth_url
        logger.info(f"[handle_onboarding] Response: {response_data}")
        return json.dumps(response_data)

    # Fallback to last AI message
    messages = result.get("messages", [])
    if messages:
        last_msg = messages[-1]
        message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        response_data = {
            "status": "success",
            "message": message,
        }
        logger.info(f"[handle_onboarding] Response: {response_data}")
        return json.dumps(response_data)

    return json.dumps({
        "status": "error",
        "message": "I encountered an issue processing your onboarding request. Please try again."
    })
