"""Tool for sending SMS messages to the user during agent execution.

The LLM controls ONLY the message content. All routing (phone number,
channel) is derived from the injected agent state, making it impossible
for the LLM to hallucinate delivery details.
"""

from typing import Annotated, Any

from langchain.tools import InjectedState, tool

from module.logger import get_logger

logger = get_logger(__name__)


def _extract_phone_from_thread_id(thread_id: str) -> str:
    """Extract phone number from SMS thread_id format 'sms:{phone}:{uuid}'.

    Raises:
        ValueError: If thread_id is not in the expected format.
    """
    parts = thread_id.split(":")
    if len(parts) >= 3 and parts[0] == "sms":
        return parts[1]
    raise ValueError(f"Invalid SMS thread_id format: {thread_id!r}")


def _send_sms(phone_number: str, message: str) -> None:
    """Send an SMS via the SmsService.

    Raises:
        RuntimeError: If the SMS fails to send.
    """
    from server.sms_service import SmsService

    sms_service = SmsService()
    result = sms_service.send_sms(phone_number, message)

    if not result.success:
        raise RuntimeError(f"SMS delivery failed: {result.error}")

    logger.info(f"SMS sent to {phone_number}")


def _send_message_impl(message: str, state: dict[str, Any]) -> str:
    """Core implementation for send_message, callable from tests."""
    if len(message) > 320:
        return (
            f"Error: Message is {len(message)} characters, which exceeds the 320 character SMS limit. "
            "Shorten your message and try again."
        )

    thread_id = state["thread_id"]

    try:
        phone_number = _extract_phone_from_thread_id(thread_id)
        _send_sms(phone_number, message)
        return "[Message delivered to user]"
    except (ValueError, RuntimeError) as e:
        logger.error(f"send_message failed: {e}")
        return (
            "[SMS delivery failed. "
            "Do NOT retry — the message cannot be delivered right now. "
            "End the conversation here.]"
        )


@tool
def send_message(
    message: str,
    state: Annotated[dict[str, Any], InjectedState],
) -> str:
    """Send a text message to the user. Messages must be under 320 characters.

    Args:
        message: The message to send to the user (max 320 characters).
    """
    return _send_message_impl(message, state)
