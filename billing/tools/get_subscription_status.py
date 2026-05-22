"""Tool for retrieving user subscription and usage status."""

import json
from typing import Annotated

from langchain.tools import InjectedState, tool
from pydantic import BaseModel, Field

from billing.tier import get_billing_status_by_user_id
from tools.user_context import get_user_id

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
    include_plan_details: bool = Field(default=True, description="Whether to include plan details")


@tool(args_schema=GetSubscriptionStatusInput)
def get_subscription_status(
    include_plan_details: bool = True,
    state: Annotated[dict[str, object], InjectedState] | None = None,
) -> str:
    """Get the user's current subscription tier, billing status, usage limits, and plan comparison details.

    Use this tool when:
    - User asks about their plan, subscription, or billing
    - User wants to know what features they have access to
    - User asks about pricing or what plans are available

    Returns:
        JSON string with subscription status, usage, limits, and plan details
    """
    status = get_billing_status_by_user_id(get_user_id(state))

    result: dict[str, str | int | bool | dict[str, dict[str, str | int]] | None] = {
        "tier": status["tier"],
        "status": status["status"],
    }

    if status["current_period_ends"]:
        result["current_period_ends"] = status["current_period_ends"]

    result["questions_allowed"] = status["questions_allowed"]
    result["leagues_connected"] = status["leagues_connected"]
    result["leagues_allowed"] = status["leagues_allowed"]

    if include_plan_details:
        result["plans"] = PLAN_DETAILS

    return json.dumps(result)
