"""Repository class for notification preference records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import Repository
from data.user_repository import UserRepository


class NotificationPreferenceRepository(Repository):
    """Repository for managing user notification preferences."""

    def __init__(self, session: Session | None = None) -> None:
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
        pref = self.session.execute(
            text(
                """
                SELECT
                    ui.external_id,
                    np.league_id,
                    np.notification_type,
                    np.enabled,
                    np.created_at,
                    np.updated_at
                FROM notification_preferences np
                JOIN user_identities ui
                    ON ui.user_id = np.user_id
                    AND ui.medium = :medium
                WHERE ui.external_id = :user_email
                    AND np.league_id = :league_id
                    AND np.notification_type = :notification_type
                """
            ),
            {
                "medium": Medium.EMAIL.value,
                "user_email": user_email,
                "league_id": league_id,
                "notification_type": notification_type,
            },
        ).fetchone()

        if pref is not None:
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
        user_id = UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)
        self.set_preference_by_user_id(user_id, league_id, notification_type, enabled)

    def set_preference_by_user_id(
        self, user_id: UUID, league_id: str, notification_type: str, enabled: bool
    ) -> None:
        """Set user preference by canonical user ID."""
        self.upsert(
            conflict_columns=["user_id", "league_id", "notification_type"],
            user_id=user_id,
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
                SELECT ui.external_id, np.league_id
                FROM notification_preferences np
                JOIN user_identities ui
                    ON ui.user_id = np.user_id
                    AND ui.medium = :medium1
                WHERE np.notification_type = :type1 AND np.enabled = TRUE

                UNION

                -- Users with no preference, where type default is TRUE
                SELECT DISTINCT ui.external_id, ut.league_id
                FROM yahoo_user_teams ut
                JOIN user_identities ui
                    ON ui.user_id = ut.user_id
                    AND ui.medium = :medium2
                WHERE NOT EXISTS (
                    SELECT 1 FROM notification_preferences np
                    WHERE np.user_id = ut.user_id
                    AND np.league_id = ut.league_id
                    AND np.notification_type = :type2
                )
                AND EXISTS (
                    SELECT 1 FROM notification_types nt
                    WHERE nt.type_key = :type3 AND nt.default_enabled = TRUE
                )
                """
            ),
            {
                "medium1": Medium.EMAIL.value,
                "medium2": Medium.EMAIL.value,
                "type1": notification_type,
                "type2": notification_type,
                "type3": notification_type,
            },
        ).fetchall()

        return [(str(row[0]), str(row[1])) for row in result]
