"""SMS channel dispatch for the response node."""

from agent.agent_state import AgentState
from agent.channels.text_utils import strip_markdown
from module.logger import get_logger

logger = get_logger(__name__)


def _extract_phone_from_thread_id(thread_id: str) -> str | None:
    """Extract phone number from SMS thread_id format 'sms:{phone}:{uuid}'."""
    parts = thread_id.split(":")
    if len(parts) >= 3 and parts[0] == "sms":
        return parts[1]
    return None


def send_sms_response(state: AgentState, message_content: str) -> None:
    """Send the agent response as an SMS.

    Args:
        state: Current agent state
        message_content: The AI message content to send
    """
    thread_id = state.get("thread_id")

    if not thread_id:
        logger.error("No thread_id in state, cannot send SMS")
        return

    phone_number = _extract_phone_from_thread_id(thread_id)
    if not phone_number:
        logger.error(f"Could not extract phone number from thread_id: {thread_id}")
        return

    plain_text = strip_markdown(message_content)

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
