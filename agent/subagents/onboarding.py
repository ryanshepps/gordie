"""Onboarding sub-agent for Yahoo Fantasy authentication and team setup."""

import json
import logging
from typing import Annotated, Any

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field

from agent.subagents.base import create_subagent, extract_response, invoke_subagent
from tools.oauth.generate_oauth_link import generate_oauth_link
from tools.yahoo.get_user_leagues import get_user_leagues
from tools.yahoo.onboard_user_team import onboard_user_team

logger = logging.getLogger(__name__)


class OnboardingResponse(BaseModel):
    """Structured response from the onboarding agent."""

    message: str = Field(description="The message to send to the user")
    oauth_url: str | None = Field(default=None, description="The OAuth URL if one was generated")


_onboarding_agent_task = """
Help users connect their Yahoo Fantasy account.

Flow:
1. Call generate_oauth_link to create an authorization link.
2. Once authenticated, use get_user_leagues to retrieve their leagues/teams.
3. Use onboard_user_team to save their selected team.

The user's email will be provided in a system message.
"""

_agent = create_subagent(
    name="onboarding",
    system_prompt=_onboarding_agent_task,
    tools=[generate_oauth_link, get_user_leagues, onboard_user_team],
    model="gpt-4o-mini",
    response_format=OnboardingResponse,
)


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
    logger.info(f"[handle_onboarding] Processing request for {user_email}: {request[:100]}...")

    thread_id = state.get("thread_id", user_email) if state else user_email
    result = invoke_subagent(
        agent=_agent,
        request=request,
        context_parts=[f"Current user email for this session: {user_email}"],
        thread_id=thread_id,
    )

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

    message = extract_response(result)
    response_data = {"status": "success", "message": message}
    logger.info(f"[handle_onboarding] Response: {response_data}")
    return json.dumps(response_data)
