"""Tool for retrieving user subscription and usage status."""

import json

from langchain.tools import tool
from pydantic import BaseModel, Field

from billing.tier import get_billing_status

PLAN_DETAILS: dict[str, dict[str, str | int]] = {
    "free": {
        "price": "Free",
        "questions": "Plan and billing questions only",
        "teams": 1,
        "digests": "Yes",
        "alerts": "Yes",
    },
    "hosted": {
        "price": "$10/mo",
        "questions": "Yes",
        "teams": 3,
        "digests": "Yes",
        "alerts": "Yes",
    },
}


class GetSubscriptionStatusInput(BaseModel):
    user_email: str = Field(description="User's email address")


@tool(args_schema=GetSubscriptionStatusInput)
def get_subscription_status(user_email: str) -> str:
    """Get the user's current subscription tier, billing status, usage limits, and plan comparison details.

    Use this tool when:
    - User asks about their plan, subscription, or billing
    - User wants to know what features they have access to
    - User asks about pricing or what plans are available

    Args:
        user_email: User's email address

    Returns:
        JSON string with subscription status, usage, limits, and all plan details
    """
    status = get_billing_status(user_email)

    result: dict[str, str | int | bool | dict[str, dict[str, str | int]] | None] = {
        "tier": status["tier"],
        "status": status["status"],
    }

    if status["current_period_ends"]:
        result["current_period_ends"] = status["current_period_ends"]

    result["questions_allowed"] = status["questions_allowed"]
    result["leagues_connected"] = status["leagues_connected"]
    result["leagues_allowed"] = status["leagues_allowed"]

    result["plans"] = PLAN_DETAILS

    return json.dumps(result)
