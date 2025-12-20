"""Tool to send email responses to users."""

import markdown2
from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from server.email_service import EmailService

logger = get_logger(__name__)


class SendEmailInput(BaseModel):
    """Input schema for send_email tool."""

    to_email: str = Field(description="Recipient's email address")
    subject: str = Field(description="Email subject line")
    message: str = Field(description="Email message body")


@tool(args_schema=SendEmailInput)
def send_email(to_email: str, subject: str, message: str) -> str:
    """
    Send an email to the user.

    Use this tool to send email responses to users after processing their requests.
    Only send the relevant response, not the entire conversation history.

    Args:
        to_email: Recipient's email address
        subject: Email subject line
        message: Email message body (only include current response, not history)

    Returns:
        Confirmation message about email delivery status
    """
    try:
        email_service = EmailService()

        # Convert markdown to HTML for proper email formatting
        html_body = markdown2.markdown(
            message,
            extras=["tables", "fenced-code-blocks", "strike", "cuddled-lists"],
        )

        result = email_service.send_email(
            to_email=to_email,
            subject=subject,
            text_body=message,
            html_body=html_body,
        )

        if result.success:
            logger.info(f"Email sent successfully to {to_email}")
            return f"Email sent successfully to {to_email}"
        else:
            logger.error(f"Failed to send email to {to_email}: {result.error}")
            return f"Failed to send email to {to_email}"

    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return f"Error sending email: {e!s}"
