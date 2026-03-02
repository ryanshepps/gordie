"""Delivery channel resolution for digest notifications."""

from __future__ import annotations

from dataclasses import dataclass

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
        user = repo.get_user(user_email)
        if not user:
            return EmailDelivery()

        phone_number = user[2]
        sms_opted_out = user[3]

        if phone_number and not sms_opted_out:
            return SmsDelivery(phone_number=phone_number)

        return EmailDelivery()
    finally:
        repo.close()
