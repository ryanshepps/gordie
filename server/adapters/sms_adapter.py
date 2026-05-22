"""SMS channel adapter."""

from dataclasses import dataclass

from agent.agent_state import AgentState
from data.models import Medium
from module.logger import get_logger
from server.adapters.base import ChannelConstraints, MessageFormat
from server.adapters.text_utils import strip_markdown

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SmsAdapter:
    medium: Medium = Medium.SMS

    @property
    def constraints(self) -> ChannelConstraints:
        return ChannelConstraints(max_length=800, message_format=MessageFormat.PLAIN_TEXT)

    def send(self, external_id: str, text: str, state: AgentState) -> None:
        plain_text = strip_markdown(text)

        from server.sms_service import SmsService

        try:
            sms_service = SmsService()
            result = sms_service.send_sms(external_id, plain_text)

            if result.success:
                logger.info(f"SMS sent to {external_id}, batch_id: {result.batch_id}")
            else:
                logger.error(f"Failed to send SMS to {external_id}: {result.error}")
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
