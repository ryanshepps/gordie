"""Email channel adapter."""

from dataclasses import dataclass

from agent.agent_state import AgentState
from agent.email_enrichment import enrich_email_with_player_stats
from data.models import Medium
from module.logger import get_logger
from server.adapters.base import ChannelConstraints, MessageFormat
from server.email_formatter import FooterType, format_email
from server.email_service import EmailService
from server.thread_manager import save_message_id_mapping

logger = get_logger(__name__)


def _determine_subject(original_subject: str | None, message_content: str) -> str:
    if original_subject:
        if original_subject.lower().startswith("re:"):
            return original_subject
        return f"Re: {original_subject}"

    message_lower = message_content.lower()
    comparison_keywords = ["comparison", "vs", "recommend"]
    if any(kw in message_lower for kw in comparison_keywords):
        return "Fantasy Sports Player Comparison"
    onboard_keywords = ["onboard", "connect", "authenticate"]
    if any(kw in message_lower for kw in onboard_keywords):
        return "Fantasy Sports Team Setup"
    return "Fantasy Sports Assistant Response"


@dataclass(frozen=True, slots=True)
class EmailAdapter:
    medium: Medium = Medium.EMAIL

    @property
    def constraints(self) -> ChannelConstraints:
        return ChannelConstraints(max_length=None, message_format=MessageFormat.HTML)

    def send(self, external_id: str, text: str, state: AgentState) -> None:
        thread_id = state.get("thread_id")
        original_subject = state.get("original_subject")
        league_id = state.get("league_id")
        user_id = state.get("user_id")

        subject = _determine_subject(original_subject, text)

        stats_html = None
        if user_id and league_id:
            try:
                _, stats_html = enrich_email_with_player_stats(
                    message_content=text,
                    user_id=user_id,
                    league_id=league_id,
                )
                if stats_html:
                    logger.info("Enriched email with player statistics table")
            except Exception as e:
                logger.warning(f"Failed to enrich email with player stats: {e}")

        email_content = format_email(
            content=text,
            footer_type=FooterType.BETA,
            stats_html=stats_html if stats_html else None,
        )

        try:
            email_service = EmailService()
            result = email_service.send_email(
                to_email=external_id,
                subject=subject,
                text_body=email_content.text_body,
                html_body=email_content.html_body,
                track_clicks=False,
            )

            if result.success:
                logger.info(f"Email sent successfully to {external_id}, message_id: {result.message_id}")

                if result.message_id and thread_id and user_id:
                    try:
                        save_message_id_mapping(
                            message_id=result.message_id,
                            thread_id=thread_id,
                            user_id=user_id,
                            subject=original_subject or subject,
                        )
                        logger.info(f"Saved message_id mapping: {result.message_id} -> {thread_id}")
                    except Exception as e:
                        logger.error(f"Failed to save message_id mapping: {e}")
            else:
                logger.error(f"Failed to send email to {external_id}: {result.error}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
