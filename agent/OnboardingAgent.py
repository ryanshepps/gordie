import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.yahoo.get_league_settings import get_league_settings
from tools.yahoo.get_user_leagues import get_user_leagues
from langgraph.checkpoint.memory import MemorySaver
import logging


logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")
model = ChatOpenAI(
    model="gpt-5-nano-2025-08-07"
)


gordie_persona = """
You are Gordie, a no-nonsense fantasy league assistant.
You're tough, crack a few jokes but you're not rude.
You use short sentences, slang and metaphors according to the sport you are
currently assisting with.
Never break character.
Users call you Gordie.
"""
onboarding_agent_task = gordie_persona + """
Task: Use the get_user_leagues tool to retrieve all leagues for the user and ask the
user which league they want to onboard you into. Once they select a league, acknowledge
their choice and confirm you're ready to help.
User email: {user_email}
"""
checkpointer = MemorySaver()
agent = create_agent(
    model=model,
    tools=[get_user_leagues],
    middleware=[handle_tool_errors],
    system_prompt=SystemMessage(content=onboarding_agent_task),
    checkpointer=checkpointer
)
