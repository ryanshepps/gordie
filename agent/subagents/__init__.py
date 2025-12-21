"""Sub-agents for the fantasy agent."""

from agent.subagents.onboarding import handle_onboarding
from agent.subagents.player_add import handle_player_add
from agent.subagents.player_comparison import compare_players

__all__ = ["compare_players", "handle_onboarding", "handle_player_add"]
