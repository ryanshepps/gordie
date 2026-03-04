"""Creem webhook handler for subscription lifecycle events."""

import hashlib
import hmac
import logging
import os
from collections.abc import Mapping
from typing import cast

from quart import jsonify, request

from data.subscription_repository import SubscriptionRepository
from module.logger import get_logger

WebhookValue = str | dict[str, str] | None
WebhookObject = Mapping[str, WebhookValue]


def verify_creem_signature(raw_body: bytes, signature: str) -> bool:
    webhook_secret = os.getenv("CREEM_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return False
    computed = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _get_object(data: Mapping[str, WebhookValue]) -> WebhookObject:
    obj = data.get("object")
    if isinstance(obj, dict):
        return obj
    return {}


def _extract_customer_email(obj: WebhookObject) -> str | None:
    customer = obj.get("customer")
    if isinstance(customer, dict):
        return customer.get("email")
    return None


def _extract_subscription_id(obj: WebhookObject) -> str | None:
    subscription = obj.get("subscription")
    if isinstance(subscription, dict):
        return subscription.get("id")
    if obj.get("object") == "subscription":
        obj_id = obj.get("id")
        if isinstance(obj_id, str):
            return obj_id
    return None


def _extract_customer_id(obj: WebhookObject) -> str | None:
    customer = obj.get("customer")
    if isinstance(customer, dict):
        return customer.get("id")
    return None


def _extract_product_id(obj: WebhookObject) -> str | None:
    product = obj.get("product")
    if isinstance(product, dict):
        return product.get("id")
    if isinstance(product, str):
        return product
    return None


def _extract_period_end(obj: WebhookObject) -> str | None:
    period_end = obj.get("current_period_end_date")
    if isinstance(period_end, str):
        return period_end
    subscription = obj.get("subscription")
    if isinstance(subscription, dict):
        return subscription.get("current_period_end_date")
    return None


def register_webhook_routes(app):
    @app.route("/webhooks/creem", methods=["POST"])
    async def creem_webhook():
        logger = get_logger(__name__, log_file="server.log")

        raw_body = cast(bytes, await request.get_data(as_text=False))
        signature = request.headers.get("creem-signature", "")

        if not verify_creem_signature(raw_body, signature):
            logger.warning("Creem webhook signature verification failed")
            return jsonify({"error": "Invalid signature"}), 403

        data: Mapping[str, WebhookValue] | None = await request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid body"}), 400

        event_type = data.get("eventType", "")
        logger.info(f"Creem webhook received: {event_type}")
        logger.info(f"Creem webhook payload: {data}")

        obj = _get_object(data)

        repo = SubscriptionRepository()
        try:
            if event_type == "checkout.completed":
                _handle_checkout_completed(repo, obj, logger)
            elif event_type == "subscription.active":
                _handle_subscription_active(repo, obj, logger)
            elif event_type == "subscription.paid":
                _handle_subscription_paid(repo, obj, logger)
            elif event_type == "subscription.expired":
                _handle_subscription_expired(repo, obj, logger)
            elif event_type == "subscription.canceled":
                _handle_subscription_canceled(repo, obj, logger)
            elif event_type == "subscription.paused":
                _handle_subscription_paused(repo, obj, logger)
            else:
                logger.info(f"Ignoring unhandled Creem event: {event_type}")
        except Exception as e:
            logger.error(f"Error processing Creem webhook {event_type}: {e}", exc_info=True)
            return jsonify({"error": "Processing failed"}), 500
        finally:
            repo.close()

        return jsonify({"status": "ok"}), 200


def _handle_checkout_completed(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    from server.creem_client import tier_from_product_id

    email = _extract_customer_email(obj)
    customer_id = _extract_customer_id(obj)
    subscription_id = _extract_subscription_id(obj)
    product_id = _extract_product_id(obj)
    period_end = _extract_period_end(obj)

    if not email:
        logger.warning("checkout.completed missing customer email")
        return

    tier = tier_from_product_id(product_id or "")
    repo.activate_subscription(
        user_email=email,
        creem_customer_id=customer_id or "",
        creem_subscription_id=subscription_id or "",
        tier=tier,
        current_period_ends_at=period_end or "",
    )
    logger.info(f"Activated {tier} subscription for {email}")


def _handle_subscription_active(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    from server.creem_client import tier_from_product_id

    email = _extract_customer_email(obj)
    customer_id = _extract_customer_id(obj)
    subscription_id = _extract_subscription_id(obj)
    product_id = _extract_product_id(obj)
    period_end = _extract_period_end(obj)

    if not email:
        logger.warning("subscription.active missing customer email")
        return

    tier = tier_from_product_id(product_id or "")
    repo.activate_subscription(
        user_email=email,
        creem_customer_id=customer_id or "",
        creem_subscription_id=subscription_id or "",
        tier=tier,
        current_period_ends_at=period_end or "",
    )
    logger.info(f"Activated {tier} subscription for {email} (subscription.active)")


def _handle_subscription_paid(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    subscription_id = _extract_subscription_id(obj)
    period_end = _extract_period_end(obj)

    if not subscription_id:
        logger.warning("subscription.paid missing subscription ID")
        return

    existing = repo.find_subscription_by_creem_id(subscription_id)
    if not existing:
        email = _extract_customer_email(obj)
        if email:
            from server.creem_client import tier_from_product_id

            customer_id = _extract_customer_id(obj)
            product_id = _extract_product_id(obj)
            tier = tier_from_product_id(product_id or "")
            repo.activate_subscription(
                user_email=email,
                creem_customer_id=customer_id or "",
                creem_subscription_id=subscription_id,
                tier=tier,
                current_period_ends_at=period_end or "",
            )
            logger.info(f"Activated {tier} subscription for {email} via subscription.paid (no prior record)")
            return
        logger.warning(f"subscription.paid for unknown subscription: {subscription_id}")
        return

    user_email = existing[0]
    repo.renew_subscription(
        user_email=user_email,
        current_period_ends_at=period_end or "",
    )
    logger.info(f"Renewed subscription for {user_email}")


def _handle_subscription_expired(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    subscription_id = _extract_subscription_id(obj)
    if not subscription_id:
        logger.warning("subscription.expired missing subscription ID")
        return

    existing = repo.find_subscription_by_creem_id(subscription_id)
    if not existing:
        logger.warning(f"subscription.expired for unknown subscription: {subscription_id}")
        return

    user_email = existing[0]
    repo.expire_subscription(user_email)
    logger.info(f"Expired subscription for {user_email}")


def _handle_subscription_canceled(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    subscription_id = _extract_subscription_id(obj)
    if not subscription_id:
        logger.warning("subscription.canceled missing subscription ID")
        return

    existing = repo.find_subscription_by_creem_id(subscription_id)
    if not existing:
        logger.warning(f"subscription.canceled for unknown subscription: {subscription_id}")
        return

    user_email = existing[0]
    repo.cancel_subscription(user_email)
    logger.info(f"Canceled subscription for {user_email}")


def _handle_subscription_paused(
    repo: SubscriptionRepository, obj: WebhookObject, logger: logging.Logger
) -> None:
    subscription_id = _extract_subscription_id(obj)
    if not subscription_id:
        logger.warning("subscription.paused missing subscription ID")
        return

    existing = repo.find_subscription_by_creem_id(subscription_id)
    if not existing:
        logger.warning(f"subscription.paused for unknown subscription: {subscription_id}")
        return

    user_email = existing[0]
    repo.pause_subscription(user_email)
    logger.info(f"Paused subscription for {user_email}")
