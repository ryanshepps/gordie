"""Tool to search past conversations for relevant context."""

from typing import Annotated

from langchain.tools import InjectedState, tool
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.user_context import get_user_id

logger = get_logger(__name__)


class SearchPastConversationsInput(BaseModel):
    """Input schema for search_past_conversations tool."""

    query: str = Field(
        description=(
            "What to search for in past conversations "
            "(e.g., 'dropping McDavid', 'trade advice for centers')"
        )
    )


def create_search_past_conversations_tool(store: BaseStore, *, enabled: bool = True):
    """
    Factory function to create the search tool with access to the store.

    Args:
        store: The LangGraph memory store instance

    Returns:
        A tool function that can search past conversations
    """

    @tool(args_schema=SearchPastConversationsInput)
    def search_past_conversations(
        query: str,
        state: Annotated[dict[str, object], InjectedState] | None = None,
    ) -> str:
        """
        Search past conversations with this user for relevant context.

        Use this tool when:
        - The user references a previous conversation ("remember when...", "last time...")
        - You want to check if similar advice was given before
        - The user asks about a player they previously discussed
        - You want to provide context-aware advice based on history

        Args:
            query: What to search for in past conversations
        Returns:
            Relevant past conversation summaries, or a message if none found
        """
        if not enabled:
            return "Past conversation search is currently unavailable."

        try:
            namespace = ("memories", get_user_id(state))

            results = store.search(
                namespace,
                query=query,
                limit=5,
            )

            if not results:
                return "No relevant past conversations found."

            # Format results
            output_parts = ["Here's what I found from past conversations:\n"]

            for i, item in enumerate(results, 1):
                data = item.value
                summary = data.get("summary", "No summary available")
                players = data.get("players_mentioned", [])
                decisions = data.get("decisions_made", [])
                created_at = data.get("created_at", "Unknown date")

                output_parts.append(f"\n{i}. {summary}")
                if players:
                    players_str = ", ".join(players) if isinstance(players, list) else players
                    output_parts.append(f"   Players discussed: {players_str}")
                if decisions:
                    if isinstance(decisions, list):
                        decisions_str = ", ".join(decisions)
                    else:
                        decisions_str = decisions
                    output_parts.append(f"   Decisions made: {decisions_str}")
                output_parts.append(f"   (From: {created_at})")

            return "\n".join(output_parts)

        except Exception as e:
            logger.error(f"Error searching past conversations: {e}")
            return f"Unable to search past conversations: {e}"

    return search_past_conversations
