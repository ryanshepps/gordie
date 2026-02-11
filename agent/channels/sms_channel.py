"""SMS channel dispatch for the response node."""

import os
import re

from agent.agent_state import AgentState
from module.logger import get_logger

logger = get_logger(__name__)


def _strip_markdown(text: str) -> str:
    """Convert markdown to plain text suitable for SMS.

    Removes headers, bold, italic, links, code blocks, and list markers.
    """
    # Code blocks (fenced)
    result = re.sub(r"```[\s\S]*?```", "", text)
    # Inline code
    result = re.sub(r"`([^`]+)`", r"\1", result)
    # Headers
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)
    # Bold
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    # Italic
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    # Links: [text](url) -> text
    result = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", result)
    # Images
    result = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", result)
    # Horizontal rules
    result = re.sub(r"^[-*_]{3,}\s*$", "", result, flags=re.MULTILINE)
    # Bullet list markers
    result = re.sub(r"^[\s]*[-*+]\s+", "- ", result, flags=re.MULTILINE)
    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _extract_phone_from_thread_id(thread_id: str) -> str | None:
    """Extract phone number from SMS thread_id format 'sms:{phone}:{uuid}'."""
    parts = thread_id.split(":")
    if len(parts) >= 3 and parts[0] == "sms":
        return parts[1]
    return None


def _get_web_thread_url(thread_id: str) -> str | None:
    """Look up the web thread URL for a given thread_id."""
    from data.web_thread_repository import WebThreadRepository

    repo = WebThreadRepository()
    try:
        web_thread = repo.get_web_thread_by_thread_id(thread_id)
        if web_thread:
            web_thread_id = str(web_thread[0])
            base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")
            return f"{base_url}/r/{web_thread_id}"
    finally:
        repo.close()
    return None


def send_sms_response(state: AgentState, message_content: str) -> None:
    """Send the agent response as an SMS.

    Args:
        state: Current agent state
        message_content: The AI message content to send
    """
    thread_id = state.get("thread_id")
    has_rich_content = state.get("has_rich_content", False)

    if not thread_id:
        logger.error("No thread_id in state, cannot send SMS")
        return

    phone_number = _extract_phone_from_thread_id(thread_id)
    if not phone_number:
        logger.error(f"Could not extract phone number from thread_id: {thread_id}")
        return

    plain_text = _strip_markdown(message_content)

    # If content is long or rich, truncate and append web link
    if has_rich_content or len(plain_text) > 300:
        web_url = _get_web_thread_url(thread_id)
        if web_url:
            # Truncate to leave room for the URL suffix
            max_body = 250
            truncated = plain_text[:max_body].rsplit(" ", 1)[0] + "..."
            plain_text = f"{truncated}\n\nFull response: {web_url}"

    from module.metrics import sms_sent_total
    from server.sms_service import SmsService

    try:
        sms_service = SmsService()
        result = sms_service.send_sms(phone_number, plain_text)

        if result.success:
            sms_sent_total.labels(status="success").inc()
            logger.info(f"SMS sent to {phone_number}, batch_id: {result.batch_id}")
        else:
            sms_sent_total.labels(status="failure").inc()
            logger.error(f"Failed to send SMS to {phone_number}: {result.error}")

    except Exception as e:
        sms_sent_total.labels(status="failure").inc()
        logger.error(f"Failed to send SMS: {e}")

    # Update thread activity
    from data.sms_thread_repository import SmsThreadRepository

    repo = SmsThreadRepository()
    try:
        repo.update_sms_thread_activity(thread_id)
    except Exception as e:
        logger.error(f"Failed to update SMS thread activity: {e}")
    finally:
        repo.close()
