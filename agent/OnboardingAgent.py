import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.yahoo.get_user_leagues import get_user_leagues
from tools.yahoo.onboard_user_team import onboard_user_team
from tools.oauth.generate_oauth_link import generate_oauth_link
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import logging


logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")
model = ChatOpenAI(
    model="gpt-5-nano-2025-08-07"
)


onboarding_agent_task = """
Task: Welcome the user to the Gordie AI agent and help them onboard their Yahoo Fantasy team.

Onboarding Flow:
1. FIRST MESSAGE: You MUST immediately call generate_oauth_link to create an authorization link 
   for the user. Do not just talk about it - actually call the tool right away.
2. Once authenticated, use get_user_leagues to retrieve their leagues/teams.
3. Ask which team they want to onboard. If there's only one active team, 
   ask if they want to onboard that specific team.
4. Use onboard_user_team to save their selected team.

IMPORTANT: 
- Only show teams with currently active seasons.
- On the very first message from a user, you MUST call the generate_oauth_link tool immediately.

User email: {user_email}
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
    middleware=[handle_tool_errors],
    system_prompt=SystemMessage(content=onboarding_agent_task),
    checkpointer=checkpointer
)
