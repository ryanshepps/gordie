"""SMS service for sending messages via Sinch REST API."""

import os
import time
from dataclasses import dataclass

import requests

from module.logger import get_logger

logger = get_logger(__name__)

SINCH_BASE_URL = "https://us.sms.api.sinch.com/xms/v1"
RETRY_DELAY_SECONDS = 2


@dataclass
class SmsResult:
    """Result of sending an SMS."""

    success: bool
    batch_id: str | None = None
    error: str | None = None


class SmsService:
    """Service for sending SMS via Sinch REST API."""

    def __init__(self):
        self.service_plan_id = os.getenv("SINCH_SERVICE_PLAN_ID")
        self.api_token = os.getenv("SINCH_API_TOKEN")
        self.from_number = os.getenv("SINCH_FROM_NUMBER")

        if not self.service_plan_id or not self.api_token or not self.from_number:
            raise ValueError(
                "SINCH_SERVICE_PLAN_ID, SINCH_API_TOKEN, and SINCH_FROM_NUMBER "
                "environment variables required"
            )

    def send_sms(self, to_phone_number: str, message: str) -> SmsResult:
        """Send an SMS via Sinch API.

        Args:
            to_phone_number: Recipient phone number (E.164 format)
            message: Text message body

        Returns:
            SmsResult with success status and batch_id if successful
        """
        url = f"{SINCH_BASE_URL}/{self.service_plan_id}/batches"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_number,
            "to": [to_phone_number],
            "body": message,
        }

        for attempt in range(2):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)

                if response.status_code >= 400 and response.status_code < 500:
                    logger.error(f"Sinch API 4xx error: {response.status_code} {response.text}")
                    return SmsResult(success=False, error=f"Client error: {response.status_code}")

                response.raise_for_status()
                data = response.json()
                batch_id = data.get("id")
                logger.info(f"SMS sent to {to_phone_number}, batch_id: {batch_id}")
                return SmsResult(success=True, batch_id=batch_id)

            except requests.exceptions.RequestException as e:
                if attempt == 0 and not (
                    isinstance(e, requests.exceptions.HTTPError)
                    and e.response is not None
                    and 400 <= e.response.status_code < 500
                ):
                    logger.warning(f"SMS send attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue

                logger.error(f"Failed to send SMS to {to_phone_number}: {e}")
                return SmsResult(success=False, error=str(e))

        logger.error(f"Failed to send SMS to {to_phone_number} after retries")
        return SmsResult(success=False, error="Max retries exceeded")
