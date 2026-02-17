"""Tool for sending proactive status messages during agent execution."""

from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)


class SendMessageInput(BaseModel):
    """Input schema for send_message tool."""

    message: str = Field(
        description="The message to send to the user. Keep under 160 characters for SMS."
    )
    channel_type: Literal["sms"] = Field(
        description="The channel to send the message through"
    )
    thread_id: str = Field(
        description="The conversation thread ID (e.g., 'sms:+1234567890:uuid' or email format)"
    )
    context: str = Field(
        default="",
        description="Optional context about what the agent is doing (e.g., 'trade_analysis', 'waiver_check')",
    )


def _extract_phone_from_thread_id(thread_id: str) -> str | None:
    """Extract phone number from SMS thread_id format 'sms:{phone}:{uuid}'."""
    parts = thread_id.split(":")
    if len(parts) >= 3 and parts[0] == "sms":
        return parts[1]
    return None


def _send_sms(phone_number: str, message: str) -> bool:
    """Send an SMS via the SmsService."""
    try:
        from server.sms_service import SmsService

        sms_service = SmsService()
        result = sms_service.send_sms(phone_number, message)

        if result.success:
            logger.info(f"Proactive SMS sent to {phone_number}")
            return True
        else:
            logger.error(f"Failed to send proactive SMS: {result.error}")
            return False

    except Exception as e:
        logger.error(f"Error sending proactive SMS: {e}")
        return False


@tool(args_schema=SendMessageInput)
def send_message(
    message: str, channel_type: Literal["sms"], thread_id: str, context: str = ""
) -> str:
    """
    Send a quick status update to the user mid-processing.

    Use this tool proactively for conversational updates like:
    - "Got it!" when you understand the request
    - "Checking stats..." before running analysis
    - "Analyzing that trade..." for trade requests
    - Casual insights like "Matthews is on fire this week!"

    Keep messages short (under 160 characters for SMS compatibility).
    Only use for the SMS channel - do not use for email.

    Args:
        message: The message to send to the user
        channel_type: The channel to send through ("sms")
        thread_id: The conversation thread ID
        context: Optional context about what you're doing

    Returns:
        Confirmation that the message was sent or an error message
    """
    # Truncate message for SMS (160 chars is standard SMS limit)
    if len(message) > 160:
        message = message[:157] + "..."

    try:
        phone_number = _extract_phone_from_thread_id(thread_id)
        if not phone_number:
            logger.error(f"Could not extract phone number from thread_id: {thread_id}")
            return "Error: Could not determine phone number for SMS"

        success = _send_sms(phone_number, message)
        if success:
            return "[Status update sent to user]"
        else:
            return "[Status update failed to send, continuing with main response]"

    except Exception as e:
        logger.error(f"Error in send_message tool: {e}", exc_info=True)
        return f"Error sending message: {e!s}"
