"""Shared PostgreSQL checkpointer for LangGraph conversation persistence."""

from agent.custom_checkpointer import CustomCheckpointer

# Create singleton instance of our custom checkpointer
checkpointer = CustomCheckpointer()
checkpointer.setup()
