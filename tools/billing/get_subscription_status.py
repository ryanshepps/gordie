"""Tool for retrieving user subscription and usage status."""

import json

from langchain.tools import tool
from pydantic import BaseModel, Field

from server.tier_enforcement import get_billing_status

PLAN_DETAILS: dict[str, dict[str, str | int]] = {
    "free": {
        "price": "Free",
        "questions_per_week": 3,
        "leagues": 1,
        "digests": "No",
        "alerts": "No",
    },
    "standard": {
        "price": "$10/mo or $80/yr",
        "questions_per_week": "Unlimited",
        "leagues": 3,
        "digests": "Yes",
        "alerts": "Yes",
    },
    "allstar": {
        "price": "$18/mo or $144/yr",
        "questions_per_week": "Unlimited",
        "leagues": "Unlimited",
        "digests": "Yes",
        "alerts": "Yes",
    },
}


class GetSubscriptionStatusInput(BaseModel):
    user_email: str = Field(description="User's email address")


@tool(args_schema=GetSubscriptionStatusInput)
def get_subscription_status(user_email: str) -> str:
    """Get the user's current subscription tier, billing status, trial info, usage limits, and plan comparison details.

    Use this tool when:
    - User asks about their plan, subscription, or billing
    - User asks how many questions they have left
    - User asks about their trial or when it expires
    - User wants to know what features they have access to
    - User asks about pricing or what plans are available

    Args:
        user_email: User's email address

    Returns:
        JSON string with subscription status, usage, limits, and all plan details
    """
    status = get_billing_status(user_email)

    result: dict[str, str | int | dict[str, dict[str, str | int]] | None] = {
        "tier": status["tier"],
        "status": status["status"],
    }

    if status["trial_days_remaining"] is not None:
        result["trial_days_remaining"] = status["trial_days_remaining"]

    if status["questions_remaining"] is not None:
        result["questions_used_this_week"] = status["questions_used_this_week"]
        result["questions_remaining"] = status["questions_remaining"]

    if status["current_period_ends"]:
        result["current_period_ends"] = status["current_period_ends"]

    result["leagues_connected"] = status["leagues_connected"]
    result["leagues_allowed"] = (
        status["leagues_allowed"] if status["leagues_allowed"] is not None else "unlimited"
    )

    result["plans"] = PLAN_DETAILS

    return json.dumps(result)
