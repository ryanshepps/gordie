"""Delivery channel resolution for digest notifications."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from data.models import Medium
from data.user_repository import UserRepository
from module.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmailDelivery:
    pass


@dataclass
class SmsDelivery:
    phone_number: str


DeliveryChannel = EmailDelivery | SmsDelivery


def resolve_delivery_channel(user_email: str) -> DeliveryChannel:
    repo = UserRepository()
    try:
        user = repo.get_by_identity(Medium.EMAIL, user_email)
        if not user:
            return EmailDelivery()

        phone_number = repo.get_identity_external_id(UUID(str(user[0])), Medium.SMS)

        if phone_number and not repo.is_sms_opted_out(phone_number):
            return SmsDelivery(phone_number=phone_number)

        return EmailDelivery()
    finally:
        repo.close()
