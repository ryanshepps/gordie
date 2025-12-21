"""Player comparison agent for fantasy hockey analysis."""

import logging
import os
import sqlite3

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.agent_state import AgentState
from middleware.state_logger import StateLoggingMiddleware
from middleware.tool_call_error_wrapper import handle_tool_errors
from tools.player_comparison.calculate_fantasy_points import calculate_fantasy_points
from tools.player_comparison.compare_players_comprehensive import compare_players_comprehensive
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_player_stats import get_player_stats

logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")


player_comparison_task = """
Task: Compare NHL players to help the user make informed fantasy hockey decisions.

Comparison Process:
1. If the user provides player names (e.g., "McDavid" or "Draisaitl"), use fuzzy_resolve_nhl_api_player_ids to get their NHL API player IDs
2. Use get_player_stats to fetch statistics for each player (requires player IDs)
3. Use calculate_fantasy_points for fantasy scoring
4. Use compare_players_comprehensive for analysis
5. Present a clear recommendation with supporting data

Important: Always resolve player names to IDs first before fetching stats. The get_player_stats tool requires numeric player IDs, not names.

User email: {user_email}
League ID: {league_id}
"""

# Use SQLite for persistent conversation storage
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)

agent = create_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[fuzzy_resolve_nhl_api_player_ids, get_player_stats, calculate_fantasy_points, compare_players_comprehensive],
    middleware=[StateLoggingMiddleware("player_comparison"), handle_tool_errors],
    system_prompt=SystemMessage(content=player_comparison_task),
    checkpointer=checkpointer,
    state_schema=AgentState,
)
