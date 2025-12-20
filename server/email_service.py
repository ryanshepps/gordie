"""
Email service for sending emails via Mailgun API.

This module provides a simple interface for sending emails using
Mailgun's HTTP API.
"""

import os
from dataclasses import dataclass

import requests

from module.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmailResult:
    """Result of sending an email."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailService:
    """Service for sending emails via Mailgun API."""

    def __init__(self):
        """
        Initialize the EmailService with Mailgun credentials from environment.

        Raises:
            ValueError: If required environment variables are missing
        """
        self.api_key = os.getenv("MAILGUN_API_KEY")
        self.domain = os.getenv("MAILGUN_DOMAIN")
        self.from_email = os.getenv("MAILGUN_FROM_EMAIL")

        if not self.api_key or not self.domain:
            raise ValueError("MAILGUN_API_KEY and MAILGUN_DOMAIN environment variables required")

        # Default from email if not specified
        if not self.from_email:
            self.from_email = f"Gordie <gordie@{self.domain}>"

    def _text_to_html(self, text: str) -> str:
        """
        Convert plain text to simple HTML email.

        Args:
            text: Plain text email body

        Returns:
            HTML formatted email body
        """
        import html

        # Escape HTML characters to prevent injection
        escaped_text = html.escape(text)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="white-space: pre-wrap;">{escaped_text}</div>
</body>
</html>"""

    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        track_opens: bool = True,
        track_clicks: bool = True,
        custom_data: dict[str, str] | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> EmailResult:
        """
        Send email via Mailgun API.

        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            html_body: Optional HTML email body
            track_opens: Enable open tracking (default: True)
            track_clicks: Enable click tracking (default: True)
            custom_data: Optional custom metadata to attach to the email
            in_reply_to: Message-ID of email being replied to (for threading)
            references: Space-separated list of Message-IDs in thread chain

        Returns:
            EmailResult with success status and message_id if successful
        """
        try:
            url = f"https://api.mailgun.net/v3/{self.domain}/messages"

            data = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "text": text_body,
                "o:tracking": "yes" if track_opens else "no",
                "o:tracking-opens": "yes" if track_opens else "no",
                "o:tracking-clicks": "yes" if track_clicks else "no",
            }

            # Add threading headers for proper email client threading
            if in_reply_to:
                data["h:In-Reply-To"] = in_reply_to
            if references:
                data["h:References"] = references

            # If no HTML body provided, auto-generate from text body
            # This ensures tracking pixels work (Mailgun needs HTML to inject pixels)
            if html_body:
                data["html"] = html_body
            else:
                # Convert text to simple HTML with proper formatting
                html_body = self._text_to_html(text_body)
                data["html"] = html_body

            # Add custom metadata for tracking specific campaigns/users
            if custom_data:
                for key, value in custom_data.items():
                    data[f"v:{key}"] = str(value)

            # Validate api_key before making request
            if not self.api_key:
                logger.error("MAILGUN_API_KEY is not set")
                return EmailResult(success=False, error="MAILGUN_API_KEY is not set")

            response = requests.post(url, auth=("api", self.api_key), data=data, timeout=10)

            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Email sent to {to_email}: {response_data}")

            # Extract Message-ID from Mailgun response
            # Mailgun returns: {"id": "<message-id@domain>", "message": "Queued..."}
            message_id = response_data.get("id")
            if message_id:
                # Clean the Message-ID (remove angle brackets)
                message_id = message_id.strip("<>")

            return EmailResult(success=True, message_id=message_id)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return EmailResult(success=False, error=str(e))
