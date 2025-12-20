"""Player add agent for finding available players, evaluating pickups, and roster decisions."""

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
from tools.player_comparison.get_player_stats import get_player_stats
from tools.player_comparison.resolve_player_names import resolve_player_names
from tools.subagents.compare_players import compare_players
from tools.yahoo.filter_players_by_nhl_team import filter_players_by_nhl_team
from tools.yahoo.get_available_players import get_available_players
from tools.yahoo.get_league_players import get_league_players
from tools.yahoo.get_league_teams import get_league_teams
from tools.yahoo.get_roster import get_roster
from tools.yahoo.get_team_roster import get_team_roster

logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

player_add_task = """
You help users find players to add, trade, or drop from their fantasy hockey roster.

CRITICAL RULES:
1. You MUST call tools to get real data. NEVER give generic advice.
2. ALWAYS call get_roster FIRST to see the user's current players.
3. ALWAYS call get_available_players or filter_players_by_nhl_team to find replacement options.
4. Your final response must include SPECIFIC player names with real stats.

TOOLS:

get_roster(user_email, league_id, team_id)
- Get user's current roster. CALL THIS FIRST.

get_available_players(user_email, league_id, status, position, count)
- Find free agents (status="FA") or waiver players (status="W") or all (status="A")

filter_players_by_nhl_team(user_email, league_id, nhl_teams, mode, status, position, count)
- Find players NOT on specific NHL teams: mode="exclude", nhl_teams=["TB", "FLA"]
- Find players ON specific NHL teams: mode="include"

get_league_teams(user_email, league_id)
- Get all fantasy teams and their managers (for proposing trades)

get_team_roster(user_email, league_id, team_id)
- Get any team's roster to scout for trade targets

get_league_players(user_email, league_id, status, position, search, count, sort)
- Search players. status="T" for taken/rostered players only.

compare_players(request, user_email, league_id)
- Compare players using stats and fantasy scoring

WORKFLOW FOR "I have too many [Team] players, help me trade":

1. Call get_roster → identify players from that NHL team
2. Call filter_players_by_nhl_team with mode="exclude" and nhl_teams=[team] → find available replacements NOT on that team
3. Call compare_players → compare your players vs available options
4. If good waiver options exist → recommend specific pickups with who to drop
5. If no good waivers:
   a. Call get_league_teams → get all fantasy teams and managers
   b. Call get_league_players with status="T" → find owned players at same positions
   c. Call compare_players → find fair trade matches
   d. Recommend: "Trade [Your Player] to [Manager Name]'s team for [Their Player]"

RESPONSE FORMAT:
- List the specific players to trade/drop with their current fantasy points
- List the specific replacement players with their stats
- For trades, include the fantasy team manager name
- Explain WHY each move makes sense based on the stats

User email: {user_email}
League ID: {league_id}
Team ID: {team_id}
"""

# Use SQLite for persistent conversation storage
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)

agent = create_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[
        # Yahoo Fantasy tools
        get_available_players,
        get_league_players,
        get_roster,
        get_league_teams,
        get_team_roster,
        filter_players_by_nhl_team,
        # Player comparison sub-agent
        compare_players,
        # Direct player stats tools (for detailed analysis)
        resolve_player_names,
        get_player_stats,
        calculate_fantasy_points,
        compare_players_comprehensive,
    ],
    middleware=[StateLoggingMiddleware("player_add"), handle_tool_errors],
    system_prompt=SystemMessage(content=player_add_task),
    checkpointer=checkpointer,
    state_schema=AgentState,
)
