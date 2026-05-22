"""Tool for generating Creem checkout links."""

from langchain.tools import tool
from pydantic import BaseModel, Field

from billing.creem_client import create_checkout_session
from module.logger import get_logger

logger = get_logger(__name__)

VALID_PLANS = frozenset({"hosted_monthly"})

PLAN_DESCRIPTIONS: dict[str, str] = {
    "hosted_monthly": "Hosted ($10/mo)",
}


class GenerateCheckoutLinkInput(BaseModel):
    user_email: str = Field(description="User's email address")
    plan: str = Field(description="Plan to generate checkout for: hosted_monthly")


@tool(args_schema=GenerateCheckoutLinkInput)
def generate_checkout_link(user_email: str, plan: str) -> str:
    """Generate a checkout link for the user to upgrade their subscription.

    Use this tool when:
    - User wants to upgrade to a paid plan
    - User asks how to subscribe or pay
    - You need to include a checkout link in an upgrade suggestion

    Args:
        user_email: User's email address
        plan: hosted_monthly

    Returns:
        Checkout URL the user can visit to complete payment
    """
    if plan not in VALID_PLANS:
        return f"Invalid plan '{plan}'. Valid plans: {', '.join(sorted(VALID_PLANS))}"

    try:
        checkout_url = create_checkout_session(plan, user_email)
        plan_label = PLAN_DESCRIPTIONS[plan]
        logger.info(f"Generated checkout link for {user_email}: {plan}")
        return f"{plan_label}: {checkout_url}"
    except Exception as e:
        logger.error(f"Failed to generate checkout link for {user_email}/{plan}: {e}")
        return "Sorry, I couldn't generate a checkout link right now. Please try again in a moment."
