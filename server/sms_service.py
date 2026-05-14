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
    """Service for sending SMS via Sinch REST API.

    Constructable without credentials — `enabled` is False and send_sms returns
    an error result rather than raising. This lets the server run email-only.
    """

    def __init__(self) -> None:
        self.service_plan_id = os.getenv("SINCH_SERVICE_PLAN_ID")
        self.api_token = os.getenv("SINCH_API_TOKEN")
        self.from_number = os.getenv("SINCH_FROM_NUMBER")
        self.enabled = bool(self.service_plan_id and self.api_token and self.from_number)

        if not self.enabled:
            logger.warning(
                "SmsService disabled: SINCH_SERVICE_PLAN_ID / SINCH_API_TOKEN / "
                "SINCH_FROM_NUMBER not all set"
            )

    def send_sms(self, to_phone_number: str, message: str) -> SmsResult:
        """Send an SMS via Sinch API.

        Args:
            to_phone_number: Recipient phone number (E.164 format)
            message: Text message body

        Returns:
            SmsResult with success status and batch_id if successful
        """
        if not self.enabled:
            logger.warning(f"Skipping SMS to {to_phone_number}: SmsService not configured")
            return SmsResult(success=False, error="sms_disabled")

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
