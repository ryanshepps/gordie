"""Thin wrapper around the Creem.io REST API."""

import os

import requests
from dotenv import load_dotenv

from module.logger import get_logger

load_dotenv()

logger = get_logger(__name__, log_file="server.log")

CREEM_API_BASE_URL = os.getenv("CREEM_API_BASE_URL", "https://test-api.creem.io/v1")
CREEM_API_KEY = os.getenv("CREEM_API_KEY", "")

PRODUCT_IDS = {
    "standard_monthly": os.getenv("CREEM_PRODUCT_STANDARD_MONTHLY", ""),
    "standard_annual": os.getenv("CREEM_PRODUCT_STANDARD_ANNUAL", ""),
}

PRODUCT_ID_TO_TIER = {
    os.getenv("CREEM_PRODUCT_STANDARD_MONTHLY", ""): "standard",
    os.getenv("CREEM_PRODUCT_STANDARD_ANNUAL", ""): "standard",
}


def _headers() -> dict[str, str]:
    return {
        "x-api-key": CREEM_API_KEY,
        "Content-Type": "application/json",
    }


def create_checkout_session(
    plan: str,
    customer_email: str,
    success_url: str | None = None,
) -> str:
    product_id = PRODUCT_IDS.get(plan)
    if not product_id:
        raise ValueError(f"Unknown plan: {plan}")

    payload: dict[str, str | dict[str, str]] = {
        "product_id": product_id,
        "customer": {"email": customer_email},
    }
    if success_url:
        payload["success_url"] = success_url

    response = requests.post(
        f"{CREEM_API_BASE_URL}/checkouts",
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["checkout_url"]


def get_billing_portal_link(creem_customer_id: str) -> str:
    response = requests.post(
        f"{CREEM_API_BASE_URL}/customers/billing",
        json={"customer_id": creem_customer_id},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["customer_portal_link"]


def get_subscription(creem_subscription_id: str) -> dict[str, str]:
    response = requests.get(
        f"{CREEM_API_BASE_URL}/subscriptions",
        params={"subscription_id": creem_subscription_id},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_customer_by_email(email: str) -> dict[str, str] | None:
    response = requests.get(
        f"{CREEM_API_BASE_URL}/customers",
        params={"email": email},
        headers=_headers(),
        timeout=15,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def tier_from_product_id(product_id: str) -> str:
    return PRODUCT_ID_TO_TIER.get(product_id, "standard")
