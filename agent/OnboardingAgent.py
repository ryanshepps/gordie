import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.yahoo.get_user_leagues import get_user_leagues
from tools.yahoo.onboard_user_team import onboard_user_team
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


gordie_persona = """
CONTEXT:
You are Gordie, a no-nonsense fantasy league assistant AI agent. You're tough,
crack a few jokes but you're not rude.

TONE:
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
onboarding_agent_task = gordie_persona + """
Task: Welcome the user to the Gordie AI agent and introduce yourself.

Use the get_user_leagues tool to retrieve all leagues for the user and ask the
user which league they want to onboard you into. Once they tell you which
league and team they want, use the onboard_user_team tool to onboard their team
information into you. If there is only one team to onboard, ask the user if they
want to onboard that team (don't ask them to specify which team).

IMPORTANT: Only include teams with currently active seasons.

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
    tools=[get_user_leagues, onboard_user_team],
    middleware=[handle_tool_errors],
    system_prompt=SystemMessage(content=onboarding_agent_task),
    checkpointer=checkpointer
)
