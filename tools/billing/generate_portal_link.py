"""Tool for generating Creem billing portal links."""

from langchain.tools import tool
from pydantic import BaseModel, Field

from data.subscription_repository import SubscriptionRepository
from module.logger import get_logger
from server.creem_client import get_billing_portal_link

logger = get_logger(__name__)


class GeneratePortalLinkInput(BaseModel):
    user_email: str = Field(description="User's email address")


@tool(args_schema=GeneratePortalLinkInput)
def generate_portal_link(user_email: str) -> str:
    """Generate a billing portal link where the user can manage their subscription.

    The billing portal lets users update payment methods, view invoices, or cancel.
    Only works for users who have an existing paid subscription.

    Use this tool when:
    - User wants to update their payment method
    - User asks to view their invoices or billing history
    - User wants to cancel their subscription
    - User asks to manage their billing

    Args:
        user_email: User's email address

    Returns:
        Billing portal URL or an error message if no subscription exists
    """
    repo = SubscriptionRepository()
    try:
        sub = repo.get_subscription(user_email)
        if not sub or not sub[1]:
            return "No active subscription found. You need to subscribe first before you can manage billing."

        creem_customer_id: str = sub[1]
        portal_url = get_billing_portal_link(creem_customer_id)
        logger.info(f"Generated portal link for {user_email}")
        return f"Billing portal: {portal_url}"
    except Exception as e:
        logger.error(f"Failed to generate portal link for {user_email}: {e}")
        return "Sorry, I couldn't generate a billing portal link right now. Please try again in a moment."
    finally:
        repo.close()
