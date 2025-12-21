"""Agent graph for the fantasy hockey assistant.

Uses a simplified supervisor pattern where sub-agents are invoked as tools
rather than separate graph nodes. This provides deterministic routing
through explicit tool calls.
"""

import logging
import os
import sqlite3
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.memory_store import get_memory_store, memory_store

# Use literal string for END to satisfy type checker
END_NODE: Literal["__end__"] = "__end__"

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["get_memory_store", "memory_store"]


def _sanitize_namespace_label(label: str) -> str:
    """
    Sanitize a string for use in LangGraph store namespace.

    LangGraph namespaces cannot contain periods, so we replace them.

    Args:
        label: The label to sanitize (e.g., email address)

    Returns:
        Sanitized label safe for namespace use
    """
    return label.replace(".", "_dot_").replace("@", "_at_")


def summarize_and_store_conversation(
    messages: list[Any],
    thread_id: str,
    user_email: str,
    store: InMemoryStore,
) -> bool:
    """
    Summarize a conversation and store it in the memory store.

    Args:
        messages: List of conversation messages
        thread_id: The conversation thread ID
        user_email: The user's email address
        store: The LangGraph memory store

    Returns:
        True if stored successfully, False otherwise
    """
    from datetime import datetime
    from typing import Any

    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel, Field

    # Need at least 2 messages (user + assistant) to summarize
    if not messages or len(messages) < 2:
        logger.debug("Not enough messages to summarize")
        return False

    # Check if we already have a memory for this thread
    # Sanitize email for namespace (can't contain periods)
    safe_email = _sanitize_namespace_label(user_email)
    namespace = ("memories", safe_email)
    existing = store.get(namespace, thread_id)
    if existing:
        logger.debug(f"Memory already exists for thread {thread_id}")
        return False

    # Build conversation text from messages
    conversation_parts = []
    for msg in messages:
        if hasattr(msg, "type") and hasattr(msg, "content"):
            role = "User" if msg.type == "human" else "Gordie"
            content = str(msg.content)
            if content and not content.startswith("system"):
                conversation_parts.append(f"{role}: {content}")
        elif isinstance(msg, dict):
            msg_type = msg.get("type") or msg.get("role")
            role = "User" if msg_type in ("human", "user") else "Gordie"
            content = msg.get("content", "")
            if content:
                conversation_parts.append(f"{role}: {content}")

    if len(conversation_parts) < 2:
        return False

    conversation_text = "\n\n".join(conversation_parts[-10:])  # Last 10 messages max

    # Define structured output for summary
    class ConversationSummary(BaseModel):
        """Structured output for conversation summarization."""

        summary: str = Field(
            description="A concise 2-3 sentence summary of what was discussed and any outcomes"
        )
        key_topics: list[str] = Field(
            description="List of main topics discussed (e.g., 'trade advice', 'waiver pickup')"
        )
        players_mentioned: list[str] = Field(
            description="List of player names that were discussed"
        )
        decisions_made: list[str] = Field(
            description="List of any decisions or actions the user took or decided on"
        )

    try:
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = model.with_structured_output(ConversationSummary)

        prompt = f"""Analyze this fantasy hockey conversation and extract key information.

Conversation:
{conversation_text}

Generate a summary that captures:
1. What the user asked about or wanted help with
2. What advice or information was provided
3. Any decisions the user made
4. Players that were specifically discussed"""

        result: Any = structured_llm.invoke(prompt)

        # Store in the memory store
        store.put(
            namespace,
            thread_id,
            {
                "summary": result.summary,
                "key_topics": result.key_topics,
                "players_mentioned": result.players_mentioned,
                "decisions_made": result.decisions_made,
                "created_at": datetime.now().isoformat(),
                "thread_id": thread_id,
            },
        )

        logger.info(f"Stored conversation memory for thread {thread_id}")
        logger.debug(f"Summary: {result.summary}")
        return True

    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}")
        return False


def is_first_message_in_thread(thread_id: str) -> bool:
    """
    Check if this is the first message in the current conversation thread.

    Args:
        thread_id: The conversation thread ID

    Returns:
        True if no previous checkpoints exist for this thread, False otherwise
    """
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )

    if not os.path.exists(db_path):
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM checkpoints
            WHERE thread_id = ?
        """,
            (thread_id,),
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count == 0

    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return True


def _format_quoted_message(original_message: str) -> str:
    """
    Format the original message as a quoted block for email replies.

    Args:
        original_message: The original user message to quote

    Returns:
        Formatted quoted text with ">" prefix on each line
    """
    lines = original_message.strip().split("\n")
    quoted_lines = [f"> {line}" for line in lines]
    return "\n".join(quoted_lines)


def _format_quoted_html(original_message: str) -> str:
    """
    Format the original message as a quoted HTML block for email replies.

    Args:
        original_message: The original user message to quote

    Returns:
        HTML formatted blockquote
    """
    import html

    escaped = html.escape(original_message.strip())
    # Preserve line breaks
    escaped = escaped.replace("\n", "<br>")

    return f"""
<div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #ccc;">
    <p style="color: #666; font-size: 12px; margin-bottom: 10px;">You wrote:</p>
    <blockquote style="margin: 0; padding: 10px 15px; border-left: 3px solid #ccc; background-color: #f9f9f9; color: #555;">
        {escaped}
    </blockquote>
</div>
"""


def email_node(state: AgentState) -> Command[Literal["__end__"]]:
    """Sends email to user with agent response and ends the flow."""
    import markdown2

    from server.email_service import EmailService
    from server.email_thread_manager import save_message_id_mapping

    # Extract last assistant message
    messages = state.get("messages", [])
    user_email = state.get("user_email")
    thread_id = state.get("thread_id")
    original_subject = state.get("original_subject")
    original_message = state.get("original_message")

    if not user_email:
        logger.error("No user email found in state, cannot send email")
        return Command(goto=END_NODE, update=state)

    # Find last AI message
    last_ai_message = None
    for msg in reversed(messages):
        # Check if it's an AI message (has .type attribute or is dict with 'type' key)
        msg_type = getattr(msg, 'type', None) or (msg.get('type') if isinstance(msg, dict) else None)
        if msg_type == 'ai':
            last_ai_message = msg
            break

    if not last_ai_message:
        logger.warning("No AI message found to send via email")
        return Command(goto=END_NODE, update=state)

    # Extract message content
    if isinstance(last_ai_message, dict):
        message_content = str(last_ai_message.get("content", ""))
    elif hasattr(last_ai_message, "content"):
        message_content = str(last_ai_message.content)
    else:
        message_content = str(last_ai_message)

    # Determine email subject
    # Use original subject with "Re: " prefix if available, otherwise generate based on content
    if original_subject:
        # Add "Re: " prefix if not already present
        if original_subject.lower().startswith("re:"):
            subject = original_subject
        else:
            subject = f"Re: {original_subject}"
    else:
        # Fallback to content-based subject for new conversations
        message_lower = message_content.lower()
        if "comparison" in message_lower or "vs" in message_lower or "recommend" in message_lower:
            subject = "Fantasy Hockey Player Comparison"
        elif "onboard" in message_lower or "connect" in message_lower or "authenticate" in message_lower:
            subject = "Fantasy Hockey Team Setup"
        else:
            subject = "Fantasy Hockey Assistant Response"

    # Build email body with quoted original message
    text_body = message_content
    if original_message:
        quoted_text = _format_quoted_message(original_message)
        text_body = f"{message_content}\n\n---\nYou wrote:\n{quoted_text}"

    # Send email directly using EmailService for better control
    try:
        email_service = EmailService()

        # Convert markdown to HTML for proper email formatting
        html_body = markdown2.markdown(
            message_content,
            extras=["tables", "fenced-code-blocks", "strike", "cuddled-lists"],
        )

        # Append quoted original message to HTML
        if original_message:
            html_body = html_body + _format_quoted_html(original_message)

        result = email_service.send_email(
            to_email=user_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        if result.success:
            logger.info(f"Email sent successfully to {user_email}, message_id: {result.message_id}")

            # Store Message-ID mapping for thread tracking
            if result.message_id and thread_id:
                try:
                    save_message_id_mapping(
                        message_id=result.message_id,
                        thread_id=thread_id,
                        user_email=user_email,
                        subject=original_subject or subject,
                    )
                    logger.info(f"Saved message_id mapping: {result.message_id} -> {thread_id}")
                except Exception as e:
                    logger.error(f"Failed to save message_id mapping: {e}")

            # Store conversation summary in memory for future context
            if thread_id and user_email:
                try:
                    summarize_and_store_conversation(
                        messages=messages,
                        thread_id=thread_id,
                        user_email=user_email,
                        store=get_memory_store(),
                    )
                except Exception as e:
                    logger.error(f"Failed to store conversation memory: {e}")
        else:
            logger.error(f"Failed to send email to {user_email}: {result.error}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")

    return Command(goto=END_NODE, update=state)


def build_agent_graph():
    """Build and return the simplified agent graph.

    The graph now has only 3 nodes:
    - controller: Supervisor that handles requests via sub-agent tools
    - clarification: Asks user for more information when needed
    - email: Sends the response to the user

    Sub-agents (onboarding, player_comparison) are now invoked as tools
    by the supervisor rather than being separate graph nodes.
    """
    from agent.SupervisorAgent import (
        clarification_node,
        supervisor_node,
    )

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes - sub-agents are now tools, not nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("email", email_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Setup persistent checkpointer
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "agent_conversations.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # Compile the graph
    return workflow.compile(checkpointer=checkpointer)


# Build the agent graph
agent = build_agent_graph()
