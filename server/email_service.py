"""
Email service for sending emails via Mailgun API.

This module provides a simple interface for sending emails using
Mailgun's HTTP API.
"""

import os
from dataclasses import dataclass
from typing import TypedDict

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

    def __init__(self) -> None:
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

        body_style = (
            "font-family: Arial, sans-serif; line-height: 1.6; color: #333; "
            "max-width: 600px; margin: 0 auto; padding: 20px;"
        )
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{body_style}">
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

    def send_trial_expiration_email(
        self,
        to_email: str,
        usage: "TrialUsageSummary",
        standard_checkout_url: str,
        allstar_checkout_url: str,
    ) -> EmailResult:
        subject = "Your Gordie trial has ended"

        text_body = (
            "Your 14-day free trial has ended.\n\n"
            "During your trial:\n"
            f"  - Questions asked: {usage['questions_asked']}\n"
            f"  - Digests received: {usage['digests_received']}\n"
            f"  - Leagues connected: {usage['leagues_connected']}\n\n"
            "You're now on the Free plan (3 questions/week, 1 league, no digests).\n\n"
            "Upgrade to keep full access:\n\n"
            f"  Standard ($10/mo): {standard_checkout_url}\n"
            f"  All-Star ($18/mo): {allstar_checkout_url}\n\n"
            "Or just reply to Gordie and ask to upgrade — he'll handle it.\n"
        )

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #E8EDF5; max-width: 600px; margin: 0 auto; padding: 20px; background: #0F0D09;">
    <div style="background: #1A1714; border: 1px solid #2A2520; border-radius: 8px; padding: 32px; margin-bottom: 24px;">
        <h1 style="font-size: 24px; margin: 0 0 16px 0; color: #F0EBE3;">Your 14-day trial has ended</h1>
        <p style="color: #9C9486; margin: 0 0 24px 0;">Here's what you accomplished with Gordie:</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 16px; background: #0F0D09; border-radius: 6px 6px 0 0; border-bottom: 1px solid #2A2520;">
                    <span style="color: #9C9486;">Questions asked</span>
                </td>
                <td style="padding: 12px 16px; background: #0F0D09; border-radius: 6px 6px 0 0; border-bottom: 1px solid #2A2520; text-align: right; font-weight: 700;">
                    {usage['questions_asked']}
                </td>
            </tr>
            <tr>
                <td style="padding: 12px 16px; background: #0F0D09; border-bottom: 1px solid #2A2520;">
                    <span style="color: #9C9486;">Digests received</span>
                </td>
                <td style="padding: 12px 16px; background: #0F0D09; border-bottom: 1px solid #2A2520; text-align: right; font-weight: 700;">
                    {usage['digests_received']}
                </td>
            </tr>
            <tr>
                <td style="padding: 12px 16px; background: #0F0D09; border-radius: 0 0 6px 6px;">
                    <span style="color: #9C9486;">Leagues connected</span>
                </td>
                <td style="padding: 12px 16px; background: #0F0D09; border-radius: 0 0 6px 6px; text-align: right; font-weight: 700;">
                    {usage['leagues_connected']}
                </td>
            </tr>
        </table>

        <p style="color: #9C9486; margin: 0 0 24px 0;">
            You're now on the Free plan (3 questions/week, 1 league, no digests). Upgrade to keep full access:
        </p>

        <table style="width: 100%; border-collapse: separate; border-spacing: 0 8px;">
            <tr>
                <td style="text-align: center; padding: 0;">
                    <a href="{standard_checkout_url}" style="display: block; padding: 14px 24px; background: #FFB800; color: #0F0D09; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 16px;">
                        Upgrade to Standard — $10/mo
                    </a>
                </td>
            </tr>
            <tr>
                <td style="text-align: center; padding: 0;">
                    <a href="{allstar_checkout_url}" style="display: block; padding: 14px 24px; background: transparent; color: #F0EBE3; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 16px; border: 1px solid #2A2520;">
                        Upgrade to All-Star — $18/mo
                    </a>
                </td>
            </tr>
        </table>

        <p style="color: #9C9486; margin: 24px 0 0 0; font-size: 14px;">
            Or just email Gordie and ask to upgrade — he'll handle it.
        </p>
    </div>
</body>
</html>"""

        return self.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            custom_data={"campaign": "trial_expiration"},
        )


class TrialUsageSummary(TypedDict):
    questions_asked: int
    digests_received: int
    leagues_connected: int
