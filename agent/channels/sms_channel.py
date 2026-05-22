"""SMS channel dispatch for the response node."""

from agent.agent_state import AgentState
from agent.channels.text_utils import strip_markdown
from module.logger import get_logger

logger = get_logger(__name__)


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

    from data.thread_repository import ThreadRepository

    repo = ThreadRepository()
    try:
        phone_number = repo.get_sms_external_id(thread_id)
    finally:
        repo.close()

    if phone_number is None:
        logger.error(f"Could not resolve SMS identity for thread_id: {thread_id}")
        return

    plain_text = strip_markdown(message_content)

    from server.sms_service import SmsService

    try:
        sms_service = SmsService()
        result = sms_service.send_sms(phone_number, plain_text)

        if result.success:
            logger.info(f"SMS sent to {phone_number}, batch_id: {result.batch_id}")
        else:
            logger.error(f"Failed to send SMS to {phone_number}: {result.error}")

    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
