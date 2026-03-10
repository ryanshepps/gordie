"""Tests to prevent onboarding-related errors from recurring.

These tests verify that tools properly validate their inputs before processing,
preventing crashes from invalid data (empty strings, non-numeric values, etc.).
"""

import pytest
from pydantic import ValidationError

from tools.yahoo.get_roster import GetRosterInput


class TestToolInputValidation:
    """Ensure tools validate inputs before processing."""

    def test_get_roster_rejects_empty_league_id(self) -> None:
        """Verify get_roster validates league_id is not empty.

        This test prevents: ValueError: invalid literal for int() with base 10: ''

        The fix adds Pydantic validation to reject empty strings before attempting
        int conversion.
        """
        with pytest.raises(ValidationError) as exc_info:
            GetRosterInput(
                user_email="test@example.com",
                league_id="",  # Empty string should be rejected
                team_id="1",
            )

        error_message = str(exc_info.value)
        assert "league_id cannot be empty" in error_message

    def test_get_roster_rejects_empty_team_id(self) -> None:
        """Verify get_roster validates team_id is not empty."""
        with pytest.raises(ValidationError) as exc_info:
            GetRosterInput(
                user_email="test@example.com",
                league_id="12345",
                team_id="",  # Empty string should be rejected
            )

        error_message = str(exc_info.value)
        assert "team_id cannot be empty" in error_message

    def test_get_roster_rejects_invalid_league_id(self) -> None:
        """Verify get_roster validates league_id is a valid number."""
        with pytest.raises(ValidationError) as exc_info:
            GetRosterInput(
                user_email="test@example.com",
                league_id="not-a-number",
                team_id="1",
            )

        error_message = str(exc_info.value)
        assert "must be a valid number" in error_message

    def test_get_roster_accepts_valid_inputs(self) -> None:
        """Verify get_roster accepts valid inputs."""
        # This should not raise
        valid_input = GetRosterInput(
            user_email="test@example.com",
            league_id="12345",
            team_id="1",
        )

        assert valid_input.league_id == "12345"
        assert valid_input.team_id == "1"
        assert valid_input.user_email == "test@example.com"
