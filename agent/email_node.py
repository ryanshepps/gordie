"""Email node for the fantasy hockey assistant graph.

Handles sending email responses to users with proper formatting.
"""

import html
import logging
from typing import Literal

import markdown2
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.email_enrichment import enrich_email_with_player_stats
from agent.memory_store import get_memory_store, summarize_and_store_conversation
from server.email_service import EmailService
from server.email_thread_manager import save_message_id_mapping

logger = logging.getLogger(__name__)

END_NODE: Literal["__end__"] = "__end__"


def _format_quoted_html(original_message: str) -> str:
    """
    Format the original message as a quoted HTML block for email replies.

    Args:
        original_message: The original user message to quote

    Returns:
        HTML formatted blockquote
    """
    escaped = html.escape(original_message.strip())
    escaped = escaped.replace("\n", "<br>")

    blockquote_style = (
        "margin: 0; padding: 10px 15px; border-left: 3px solid #ccc; "
        "background-color: #f9f9f9; color: #555;"
    )
    return f"""
<div style="margin-top: 20px;">
    <p style="color: #666; font-size: 12px; margin-bottom: 10px;">You wrote:</p>
    <blockquote style="{blockquote_style}">
        {escaped}
    </blockquote>
</div>
"""


def _get_last_ai_message(messages: list[object]) -> tuple[str | None, object | None]:
    """
    Extract the last AI message content from the message list.

    Returns:
        Tuple of (message_content, raw_message) or (None, None) if not found
    """
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", None)
        if msg_type is None and isinstance(msg, dict):
            msg_type = msg.get("type")
        if msg_type == "ai":
            if isinstance(msg, dict):
                return str(msg.get("content", "")), msg
            else:
                content = getattr(msg, "content", None)
                if content is not None:
                    return str(content), msg
                return str(msg), msg
    return None, None


def _determine_subject(original_subject: str | None, message_content: str) -> str:
    """
    Determine the email subject line.

    Args:
        original_subject: The original email subject if replying
        message_content: The message content for fallback subject generation

    Returns:
        The email subject to use
    """
    if original_subject:
        if original_subject.lower().startswith("re:"):
            return original_subject
        return f"Re: {original_subject}"

    # Fallback to content-based subject for new conversations
    message_lower = message_content.lower()
    comparison_keywords = ["comparison", "vs", "recommend"]
    if any(kw in message_lower for kw in comparison_keywords):
        return "Fantasy Hockey Player Comparison"
    onboard_keywords = ["onboard", "connect", "authenticate"]
    if any(kw in message_lower for kw in onboard_keywords):
        return "Fantasy Hockey Team Setup"
    return "Fantasy Hockey Assistant Response"


def email_node(state: AgentState) -> Command[Literal["__end__"]]:
    """Sends email to user with agent response and ends the flow."""
    messages = state.get("messages", [])
    user_email = state.get("user_email")
    thread_id = state.get("thread_id")
    original_subject = state.get("original_subject")
    original_message = state.get("original_message")

    if not user_email:
        logger.error("No user email found in state, cannot send email")
        return Command(goto=END_NODE, update=state)

    message_content, _ = _get_last_ai_message(messages)

    if not message_content:
        logger.warning("No AI message found to send via email")
        return Command(goto=END_NODE, update=state)

    subject = _determine_subject(original_subject, message_content)

    # Enrich email with player statistics table (HTML only)
    stats_html = ""
    league_id = state.get("league_id")
    if user_email and league_id:
        try:
            _, stats_html = enrich_email_with_player_stats(
                message_content=message_content,
                user_email=user_email,
                league_id=league_id,
            )
            if stats_html:
                logger.info("Enriched email with player statistics table")
        except Exception as e:
            logger.warning(f"Failed to enrich email with player stats: {e}")

    # Beta disclaimer note
    beta_note_text = "\n\nNote: Gordie is still in beta. He will make mistakes.\n"
    beta_note_html = """
<div style="margin-top: 20px;">
    <p style="color: #888; font-size: 12px; font-style: italic; margin: 0;">
        Note: Gordie is still in beta. He will make mistakes.
    </p>
</div>
"""

    # Simple text fallback for email clients that don't support HTML
    text_body = message_content + beta_note_text

    try:
        email_service = EmailService()

        html_body = markdown2.markdown(
            message_content,
            extras=["tables", "fenced-code-blocks", "strike", "cuddled-lists"],
        )

        # Add player stats table after message content
        html_body = html_body + stats_html

        if original_message:
            html_body = html_body + _format_quoted_html(original_message)

        # Add beta note at the end
        html_body = html_body + beta_note_html

        result = email_service.send_email(
            to_email=user_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

        if result.success:
            from module.metrics import emails_sent_total

            emails_sent_total.labels(status="success").inc()
            logger.info(f"Email sent successfully to {user_email}, message_id: {result.message_id}")

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
            from module.metrics import emails_sent_total

            emails_sent_total.labels(status="failure").inc()
            logger.error(f"Failed to send email to {user_email}: {result.error}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")

    return Command(goto=END_NODE, update=state)
