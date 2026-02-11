"""Email channel dispatch for the response node."""

from agent.agent_state import AgentState
from agent.email_enrichment import enrich_email_with_player_stats
from module.logger import get_logger
from server.email_formatter import FooterType, format_email
from server.email_service import EmailService
from server.thread_manager import save_message_id_mapping

logger = get_logger(__name__)


def _determine_subject(original_subject: str | None, message_content: str) -> str:
    """Determine the email subject line."""
    if original_subject:
        if original_subject.lower().startswith("re:"):
            return original_subject
        return f"Re: {original_subject}"

    message_lower = message_content.lower()
    comparison_keywords = ["comparison", "vs", "recommend"]
    if any(kw in message_lower for kw in comparison_keywords):
        return "Fantasy Hockey Player Comparison"
    onboard_keywords = ["onboard", "connect", "authenticate"]
    if any(kw in message_lower for kw in onboard_keywords):
        return "Fantasy Hockey Team Setup"
    return "Fantasy Hockey Assistant Response"


def send_email_response(state: AgentState, message_content: str) -> None:
    """Send the agent response as an email.

    Args:
        state: Current agent state
        message_content: The AI message content to send
    """
    user_email = state.get("user_email")
    thread_id = state.get("thread_id")
    original_subject = state.get("original_subject")
    league_id = state.get("league_id")

    if not user_email:
        logger.error("No user email found in state, cannot send email")
        return

    subject = _determine_subject(original_subject, message_content)

    # Enrich email with player statistics table (HTML only)
    stats_html = None
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

    email_content = format_email(
        content=message_content,
        footer_type=FooterType.BETA,
        stats_html=stats_html if stats_html else None,
    )

    try:
        email_service = EmailService()

        result = email_service.send_email(
            to_email=user_email,
            subject=subject,
            text_body=email_content.text_body,
            html_body=email_content.html_body,
            track_clicks=False,
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
        else:
            from module.metrics import emails_sent_total

            emails_sent_total.labels(status="failure").inc()
            logger.error(f"Failed to send email to {user_email}: {result.error}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
