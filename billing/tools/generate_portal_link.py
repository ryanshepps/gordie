"""Tool for generating Creem billing portal links."""

from typing import Annotated
from uuid import UUID

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field
from requests.exceptions import RequestException
from sqlalchemy.exc import SQLAlchemyError

from billing.creem_client import get_billing_portal_link
from billing.repository import SubscriptionRepository
from module.logger import get_logger
from tools.user_context import get_user_id

logger = get_logger(__name__)


class GeneratePortalLinkInput(BaseModel):
    include_link: bool = Field(default=True, description="Whether to generate the portal link")


@tool(args_schema=GeneratePortalLinkInput)
def generate_portal_link(
    include_link: bool = True,
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """Generate a billing portal link where the user can manage their subscription.

    The billing portal lets users update payment methods, view invoices, or cancel.
    Only works for users who have an existing paid subscription.

    Returns:
        Billing portal URL or an error message if no subscription exists
    """
    if not include_link:
        return "Billing portal link generation was skipped."

    user_id = get_user_id(state)
    repo = SubscriptionRepository()
    try:
        sub = repo.get_subscription_by_user_id(UUID(user_id))
        if not sub or not sub[1]:
            return "No active subscription found. You need to subscribe first before you can manage billing."

        creem_customer_id: str = sub[1]
        portal_url = get_billing_portal_link(creem_customer_id)
        logger.info(f"Generated portal link for user_id={user_id}")
        return f"Billing portal: {portal_url}"
    except (RequestException, SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to generate portal link for user_id={user_id}: {e}")
        return "Sorry, I couldn't generate a billing portal link right now. Please try again in a moment."
    finally:
        repo.close()
