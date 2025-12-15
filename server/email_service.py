"""
Email service for sending emails via Mailgun API.

This module provides a simple interface for sending emails using
Mailgun's HTTP API.
"""

import os

import requests

from module.logger import get_logger

logger = get_logger(__name__)


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

    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        track_opens: bool = True,
        track_clicks: bool = True,
        custom_data: dict | None = None,
    ) -> bool:
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

        Returns:
            True if sent successfully, False otherwise
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

            if html_body:
                data["html"] = html_body

            # Add custom metadata for tracking specific campaigns/users
            if custom_data:
                for key, value in custom_data.items():
                    data[f"v:{key}"] = str(value)

            response = requests.post(url, auth=("api", self.api_key), data=data, timeout=10)

            response.raise_for_status()
            logger.info(f"Email sent to {to_email}: {response.json()}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
