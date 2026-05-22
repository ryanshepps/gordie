"""Tool for managing user notification preferences."""

from langchain.tools import tool
from pydantic import BaseModel, Field

from data.notification_preference_repository import NotificationPreferenceRepository
from module.logger import get_logger

logger = get_logger(__name__)


class ManageNotificationsInput(BaseModel):
    """Input schema for manage_notifications tool."""

    user_email: str = Field(description="User's email address")
    league_id: str = Field(description="Yahoo league ID")
    notification_type: str = Field(description="Type of notification (e.g., 'weekly_digest')")
    enabled: bool = Field(description="Whether to enable or disable the notification")


@tool(args_schema=ManageNotificationsInput)
def manage_notifications(
    user_email: str,
    league_id: str,
    notification_type: str,
    enabled: bool,
) -> str:
    """Enable or disable a notification type for a user's league.

    Use this tool when:
    - User asks to stop receiving weekly digests or other notifications
    - User asks to turn on/off email notifications
    - User mentions "unsubscribe" or "stop sending" notifications

    Args:
        user_email: User's email address
        league_id: Yahoo league ID
        notification_type: Type of notification (e.g., "weekly_digest")
        enabled: Whether to enable or disable the notification

    Returns:
        Confirmation message about the preference change
    """
    repo = NotificationPreferenceRepository()
    try:
        repo.set_preference(user_email, league_id, notification_type, enabled)
    finally:
        repo.close()

    action = "enabled" if enabled else "disabled"
    type_display = notification_type.replace("_", " ").title()

    logger.info(
        f"Notification preference updated: {user_email}/{league_id} - "
        f"{notification_type} = {enabled}"
    )

    return f"{type_display} has been {action} for this league."
