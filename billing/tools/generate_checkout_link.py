"""Tool for generating Creem checkout links."""

from typing import Annotated
from uuid import UUID

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field
from requests.exceptions import RequestException

from billing.creem_client import create_checkout_session
from data.models import Medium
from data.user_repository import UserRepository
from module.logger import get_logger
from tools.user_context import get_user_id

logger = get_logger(__name__)

VALID_PLANS = frozenset({"hosted_monthly"})

PLAN_DESCRIPTIONS: dict[str, str] = {
    "hosted_monthly": "Hosted ($10/mo)",
}


class GenerateCheckoutLinkInput(BaseModel):
    plan: str = Field(description="Plan to generate checkout for: hosted_monthly")


def _email_for_user_id(user_id: str) -> str | None:
    repo = UserRepository()
    try:
        return repo.get_identity_external_id(UUID(user_id), Medium.EMAIL)
    finally:
        repo.close()


@tool(args_schema=GenerateCheckoutLinkInput)
def generate_checkout_link(
    plan: str,
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """Generate a checkout link for the user to upgrade their subscription.

    Use this tool when:
    - User wants to upgrade to the paid hosted plan
    - User asks how to subscribe or pay
    - You need to include a checkout link in an upgrade suggestion

    Returns:
        Checkout URL the user can visit to complete payment
    """
    if plan not in VALID_PLANS:
        return f"Invalid plan. Valid plans: {', '.join(sorted(VALID_PLANS))}"

    user_email = _email_for_user_id(get_user_id(state))
    if not user_email:
        return (
            "Sorry, I couldn't find an email address for checkout. Please connect your email first."
        )

    try:
        checkout_url = create_checkout_session(plan, user_email)
        plan_label = PLAN_DESCRIPTIONS[plan]
        logger.info(f"Generated checkout link for {user_email}: {plan}")
        return f"{plan_label}: {checkout_url}"
    except (RequestException, ValueError) as e:
        logger.error(f"Failed to generate checkout link for {user_email}/{plan}: {e}")
        return "Sorry, I couldn't generate a checkout link right now. Please try again in a moment."
