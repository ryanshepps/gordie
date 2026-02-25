"""Tool for sending proactive status messages during agent execution."""

from typing import Annotated, Any, Literal

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field

from module.logger import get_logger

logger = get_logger(__name__)


class SendMessageInput(BaseModel):
    """Input schema for send_message tool."""

    message: str = Field(
        description="The message to send to the user. Must be under 320 characters for SMS."
    )
    channel_type: Literal["sms"] = Field(
        description="The channel to send the message through"
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
    message: str,
    channel_type: Literal["sms"],
    context: str = "",
    state: Annotated[dict[str, Any], InjectedState] | None = None,
) -> str:
    """
    Send an SMS message to the user. This is the PRIMARY way to communicate with SMS users.

    Use this tool to send your full response to the user over SMS. Messages must be
    under 320 characters. If your message is too long, shorten it and try again.

    Args:
        message: The message to send to the user (max 320 characters)
        channel_type: The channel to send through ("sms")
        context: Optional context about what you're doing

    Returns:
        Confirmation that the message was sent or an error message
    """
    if len(message) > 320:
        return (
            f"Error: Message is {len(message)} characters, which exceeds the 320 character SMS limit. "
            "Shorten your message and try again."
        )

    thread_id = (state or {}).get("thread_id", "")

    try:
        phone_number = _extract_phone_from_thread_id(thread_id)
        if not phone_number:
            logger.error(f"Could not extract phone number from thread_id: {thread_id}")
            return (
                "[FATAL: SMS delivery is not possible — no valid phone number in session. "
                "Do NOT retry. End the conversation here.]"
            )

        success = _send_sms(phone_number, message)
        if success:
            return "[Message delivered to user]"
        else:
            return (
                "[SMS delivery failed due to a service outage. "
                "Do NOT retry — the message cannot be delivered right now. "
                "End the conversation here.]"
            )

    except Exception as e:
        logger.error(f"Error in send_message tool: {e}", exc_info=True)
        return f"Error sending message: {e!s}"
