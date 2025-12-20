import logging
import os
import sqlite3

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field

from agent.agent_state import AgentState
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.oauth.generate_oauth_link import generate_oauth_link
from tools.yahoo.get_user_leagues import get_user_leagues
from tools.yahoo.onboard_user_team import onboard_user_team

logger = logging.getLogger(__name__)


class OnboardingResponse(BaseModel):
    """Structured response from the onboarding agent."""

    message: str = Field(description="The message to send to the user")
    oauth_url: str | None = Field(default=None, description="The OAuth URL if one was generated")


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


onboarding_agent_task = """
Help users connect their Yahoo Fantasy account.

Flow:
1. Call generate_oauth_link to create an authorization link.
2. Once authenticated, use get_user_leagues to retrieve their leagues/teams.
3. Use onboard_user_team to save their selected team.

The user's email will be provided in a system message.
"""

# Use SQLite for persistent conversation storage across script runs
# Store in the data directory with your other persistent data
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create a SQLite connection and initialize the checkpointer
# This connection will persist across script runs via the DB file
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)

agent = create_agent(
    model=model,
    tools=[generate_oauth_link, get_user_leagues, onboard_user_team],
    middleware=[StateLoggingMiddleware("onboarding"), handle_tool_errors],
    system_prompt=SystemMessage(content=onboarding_agent_task),
    checkpointer=checkpointer,
    state_schema=AgentState,
    response_format=OnboardingResponse,
)
