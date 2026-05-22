"""Tool for generating Creem checkout links."""

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from server.creem_client import create_checkout_session

logger = get_logger(__name__)

VALID_PLANS = frozenset(
    {"standard_monthly", "standard_annual", "allstar_monthly", "allstar_annual"}
)

PLAN_DESCRIPTIONS: dict[str, str] = {
    "standard_monthly": "Standard ($10/mo)",
    "standard_annual": "Standard ($80/yr — save 33%)",
    "allstar_monthly": "All-Star ($18/mo)",
    "allstar_annual": "All-Star ($144/yr — save 33%)",
}


class GenerateCheckoutLinkInput(BaseModel):
    user_email: str = Field(description="User's email address")
    plan: str = Field(
        description="Plan to generate checkout for: standard_monthly, standard_annual, allstar_monthly, or allstar_annual"
    )


@tool(args_schema=GenerateCheckoutLinkInput)
def generate_checkout_link(user_email: str, plan: str) -> str:
    """Generate a checkout link for the user to upgrade their subscription.

    Use this tool when:
    - User wants to upgrade to a paid plan
    - User asks how to subscribe or pay
    - User wants to switch from monthly to annual or vice versa
    - You need to include a checkout link in an upgrade suggestion

    Args:
        user_email: User's email address
        plan: One of: standard_monthly, standard_annual, allstar_monthly, allstar_annual

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
