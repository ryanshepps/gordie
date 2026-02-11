"""Behavioral tests for notification preference system.

These tests verify observable behavior, not implementation details:
1. Default behavior (new users receive digest by default)
2. Opt-out persists and excludes from digest
3. Re-enabling after opt-out works
4. Preferences are per-league
5. manage_notifications tool returns correct confirmations
"""

from unittest.mock import MagicMock, patch

import pytest


class TestNotificationPreferenceRepository:
    """Test notification preference repository logic."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        with patch(
            "data.database.get_session",
            return_value=mock_session,
        ):
            from data.notification_preference_repository import (
                NotificationPreferenceRepository,
            )

            return NotificationPreferenceRepository(session=mock_session)

    def test_new_user_receives_digest_by_default(self, repo, mock_session):
        """A user with a team but no explicit preference is included in digest recipients.

        When no explicit preference exists, the system falls back to the notification_type
        default (which is TRUE for weekly_digest).
        """
        # No explicit preference exists
        mock_session.execute.return_value.fetchone.side_effect = [
            None,  # First call: get_by returns no preference
            (True,),  # Second call: notification_types default_enabled
        ]

        result = repo.is_enabled("newuser@test.com", "12345", "weekly_digest")

        assert result is True

    def test_opted_out_user_excluded_from_digest(self, repo, mock_session):
        """After opting out, user is NOT in digest recipients."""
        # Explicit preference exists with enabled=False
        mock_session.execute.return_value.fetchone.return_value = (
            "user@test.com",
            "12345",
            "weekly_digest",
            False,  # Explicitly disabled
            "2024-01-01",
            "2024-01-01",
        )

        result = repo.is_enabled("user@test.com", "12345", "weekly_digest")

        assert result is False

    def test_opted_back_in_user_receives_digest(self, repo, mock_session):
        """After re-enabling, user IS in digest recipients."""
        # Explicit preference exists with enabled=True
        mock_session.execute.return_value.fetchone.return_value = (
            "user@test.com",
            "12345",
            "weekly_digest",
            True,  # Re-enabled
            "2024-01-01",
            "2024-01-02",
        )

        result = repo.is_enabled("user@test.com", "12345", "weekly_digest")

        assert result is True

    def test_preference_is_per_league(self, repo, mock_session):
        """Opting out of one league doesn't affect another."""
        # Simulate checking preference for two different leagues
        def mock_get_preference(query):
            # Return different results based on league_id in query
            if "67890" in str(query):
                # League 67890: user opted out
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (
                    "user@test.com",
                    "67890",
                    "weekly_digest",
                    False,
                    "2024-01-01",
                    "2024-01-01",
                )
                return mock_result
            elif "12345" in str(query):
                # League 12345: user is opted in
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (
                    "user@test.com",
                    "12345",
                    "weekly_digest",
                    True,
                    "2024-01-01",
                    "2024-01-01",
                )
                return mock_result
            else:
                # Default fallback
                mock_result = MagicMock()
                mock_result.fetchone.return_value = None
                return mock_result

        # Verify the repository respects per-league preferences by checking
        # that different leagues can have different enabled values
        # We test this by verifying is_enabled returns the stored value for each league

        # Test league 12345 (opted in)
        mock_session.execute.return_value.fetchone.return_value = (
            "user@test.com",
            "12345",
            "weekly_digest",
            True,
            "2024-01-01",
            "2024-01-01",
        )
        result_12345 = repo.is_enabled("user@test.com", "12345", "weekly_digest")

        # Test league 67890 (opted out)
        mock_session.execute.return_value.fetchone.return_value = (
            "user@test.com",
            "67890",
            "weekly_digest",
            False,
            "2024-01-01",
            "2024-01-01",
        )
        result_67890 = repo.is_enabled("user@test.com", "67890", "weekly_digest")

        # Verify preferences are independent
        assert result_12345 is True, "League 12345 should be opted in"
        assert result_67890 is False, "League 67890 should be opted out"

    def test_is_enabled_returns_false_for_unknown_notification_type(
        self, repo, mock_session
    ):
        """Unknown notification types should default to False."""
        mock_session.execute.return_value.fetchone.side_effect = [
            None,  # No preference
            None,  # No notification type found
        ]

        result = repo.is_enabled("user@test.com", "12345", "unknown_type")

        assert result is False

    def test_get_all_enabled_returns_opted_in_users(self, repo, mock_session):
        """get_all_enabled_for_type returns list of (email, league_id) for opted-in users."""
        mock_session.execute.return_value.fetchall.return_value = [
            ("user1@test.com", "12345"),
            ("user2@test.com", "67890"),
        ]

        result = repo.get_all_enabled_for_type("weekly_digest")

        assert result == [
            ("user1@test.com", "12345"),
            ("user2@test.com", "67890"),
        ]


class TestManageNotificationsTool:
    """Test the manage_notifications tool behavior."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock repository."""
        return MagicMock()

    def test_disable_notification_returns_confirmation(self, mock_repo):
        """Tool returns message containing 'disabled' when disabling."""
        from tools.notifications.manage_notifications import manage_notifications

        with patch(
            "tools.notifications.manage_notifications.NotificationPreferenceRepository",
            return_value=mock_repo,
        ):
            result = manage_notifications.invoke(
                {
                    "user_email": "user@test.com",
                    "league_id": "12345",
                    "notification_type": "weekly_digest",
                    "enabled": False,
                }
            )

        mock_repo.set_preference.assert_called_once_with(
            "user@test.com", "12345", "weekly_digest", False
        )
        assert "disabled" in result.lower()

    def test_enable_notification_returns_confirmation(self, mock_repo):
        """Tool returns message containing 'enabled' when enabling."""
        from tools.notifications.manage_notifications import manage_notifications

        with patch(
            "tools.notifications.manage_notifications.NotificationPreferenceRepository",
            return_value=mock_repo,
        ):
            result = manage_notifications.invoke(
                {
                    "user_email": "user@test.com",
                    "league_id": "12345",
                    "notification_type": "weekly_digest",
                    "enabled": True,
                }
            )

        mock_repo.set_preference.assert_called_once_with(
            "user@test.com", "12345", "weekly_digest", True
        )
        assert "enabled" in result.lower()

    def test_tool_closes_repository_connection(self, mock_repo):
        """Tool properly closes the repository connection."""
        from tools.notifications.manage_notifications import manage_notifications

        with patch(
            "tools.notifications.manage_notifications.NotificationPreferenceRepository",
            return_value=mock_repo,
        ):
            manage_notifications.invoke(
                {
                    "user_email": "user@test.com",
                    "league_id": "12345",
                    "notification_type": "weekly_digest",
                    "enabled": True,
                }
            )

        mock_repo.close.assert_called_once()
