"""Repository class for notification preference records."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repository import Repository


class NotificationPreferenceRepository(Repository):
    """Repository for managing user notification preferences."""

    def __init__(self, session: Session | None = None):
        """Initialize notification preference repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("notification_preferences", session)

    def is_enabled(self, user_email: str, league_id: str, notification_type: str) -> bool:
        """Check if a notification is enabled for a user+league.

        Falls back to the notification_type default if no explicit preference exists.

        Args:
            user_email: User's email address
            league_id: Yahoo league ID
            notification_type: Type of notification (e.g., "weekly_digest")

        Returns:
            True if notification is enabled, False otherwise
        """
        # Check for explicit preference
        pref = self.get_by(
            user_email=user_email,
            league_id=league_id,
            notification_type=notification_type,
        )

        if pref is not None:
            # Column order: user_email, league_id, notification_type, enabled, created_at, updated_at
            return bool(pref[3])

        # Fall back to notification type default
        result = self.session.execute(
            text("SELECT default_enabled FROM notification_types WHERE type_key = :type_key"),
            {"type_key": notification_type},
        ).fetchone()

        if result is not None:
            return bool(result[0])

        # If notification type doesn't exist, default to False
        return False

    def set_preference(
        self, user_email: str, league_id: str, notification_type: str, enabled: bool
    ) -> None:
        """Set user preference for a notification type.

        Args:
            user_email: User's email address
            league_id: Yahoo league ID
            notification_type: Type of notification (e.g., "weekly_digest")
            enabled: Whether to enable or disable the notification
        """
        self.upsert(
            conflict_columns=["user_email", "league_id", "notification_type"],
            user_email=user_email,
            league_id=league_id,
            notification_type=notification_type,
            enabled=enabled,
            updated_at=datetime.now(),
        )

    def get_all_enabled_for_type(self, notification_type: str) -> list[tuple[str, str]]:
        """Get all (user_email, league_id) pairs where this notification is enabled.

        Includes users with no explicit preference when the type default is enabled.

        Args:
            notification_type: Type of notification (e.g., "weekly_digest")

        Returns:
            List of (user_email, league_id) tuples
        """
        result = self.session.execute(
            text(
                """
                -- Users with explicit enabled=TRUE
                SELECT user_email, league_id FROM notification_preferences
                WHERE notification_type = :type1 AND enabled = TRUE

                UNION

                -- Users with no preference, where type default is TRUE
                SELECT DISTINCT ut.user_email, ut.league_id
                FROM yahoo_user_teams ut
                WHERE NOT EXISTS (
                    SELECT 1 FROM notification_preferences np
                    WHERE np.user_email = ut.user_email
                    AND np.league_id = ut.league_id
                    AND np.notification_type = :type2
                )
                AND EXISTS (
                    SELECT 1 FROM notification_types nt
                    WHERE nt.type_key = :type3 AND nt.default_enabled = TRUE
                )
                """
            ),
            {"type1": notification_type, "type2": notification_type, "type3": notification_type},
        ).fetchall()

        return [(str(row[0]), str(row[1])) for row in result]
