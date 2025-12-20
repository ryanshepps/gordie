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
from tools.yahoo.get_available_players import get_available_players
from tools.yahoo.get_league_players import get_league_players
from tools.yahoo.get_roster import get_roster

logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

player_add_task = """
Task: Help the user find and evaluate players to add to their fantasy hockey roster.

You have access to tools for:
1. Finding available players (free agents and waivers)
2. Searching for specific players in the league
3. Getting the user's current roster
4. Comparing players to make pickup/trade decisions

WORKFLOW FOR PLAYER PICKUPS:

Step 1: Understand the Request
- Determine if the user wants to find available players, search for a specific player, or evaluate a potential add
- Ask clarifying questions if needed (position preference, specific player name, etc.)

Step 2: Gather Information
- Use get_available_players to see who is on waivers (status="W") or free agents (status="FA") or all available (status="A")
- Use get_league_players to search for specific players or browse by position
- Use get_roster to see the user's current roster

Step 3: Compare Players
- When evaluating whether to pick up a player, use the compare_players tool to compare them against:
  a) A specific player on the user's roster they might drop
  b) The weakest player at that position on the user's roster
- The compare_players tool will use advanced stats and fantasy point calculations

Step 4: Make a Recommendation
- Provide a clear recommendation with reasoning
- Explain the trade-offs (who to drop, waiver priority considerations, etc.)
- Consider positional needs and roster balance

AVAILABLE TOOLS:

1. get_available_players(user_email, league_id, status, position, count)
   - status: "A" (all available), "FA" (free agents), "W" (waivers)
   - Use this to find players that can be picked up

2. get_league_players(user_email, league_id, status, position, search, count, sort)
   - Use this to search for specific players or browse by criteria
   - status: "" (all), "A" (available), "FA", "W", "T" (taken/rostered)

3. get_roster(user_email, league_id, team_id)
   - Get the user's current roster to see who they have

4. compare_players(request, user_email, league_id)
   - Compare two or more players using advanced stats and fantasy scoring
   - Use this to evaluate whether a pickup is worth it

5. resolve_player_names(player_names)
   - Convert player names to NHL API IDs for detailed stats lookup

6. get_player_stats(player_ids, time_period)
   - Get detailed stats for players (requires NHL API player IDs)

7. calculate_fantasy_points(player_stats, league_id, user_email)
   - Calculate fantasy points based on league scoring settings

8. compare_players_comprehensive(player_stats, fantasy_points, player_positions)
   - Comprehensive multi-dimensional player comparison

EXAMPLE SCENARIOS:

User: "Who should I pick up at center?"
1. Use get_available_players with position="C" and status="A"
2. Use get_roster to see current centers on roster
3. Use compare_players to compare top available centers vs weakest rostered center
4. Recommend the best pickup with rationale

User: "Is Player X available? Should I pick him up?"
1. Use get_league_players with search="Player X" to find the player
2. Check if they're available (status in response)
3. If available, use get_roster to see current roster
4. Use compare_players to evaluate against relevant rostered players
5. Make recommendation

User: "Who is available on waivers?"
1. Use get_available_players with status="W"
2. Present the list of waiver players with their positions and teams

IMPORTANT NOTES:
- Always check the user's current roster before recommending drops
- Consider fantasy point projections, not just raw stats
- Waiver claims use priority - mention if a player is on waivers vs free agent
- Be specific about who to drop when recommending a pickup

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
