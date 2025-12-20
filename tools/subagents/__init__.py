"""Subagent tools that wrap specialized agents as callable tools."""

from tools.subagents.compare_players import compare_players
from tools.subagents.handle_onboarding import handle_onboarding
from tools.subagents.handle_player_add import handle_player_add

__all__ = ["compare_players", "handle_onboarding", "handle_player_add"]
