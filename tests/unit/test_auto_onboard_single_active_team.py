"""Unit tests for auto-onboarding when user has exactly one active team.

Verifies that _handle_no_teams_in_db auto-onboards a single active team
instead of asking the user to choose.
"""

from unittest.mock import patch

from agent.context_validator import _handle_no_teams_in_db

ACTIVE_TEAM = {
    "sport": "nhl",
    "season": "2025",
    "game_key": "465",
    "league_id": "26455",
    "team_id": "9",
    "team_name": "Steamys Dumps",
    "is_active": True,
}

OFFSEASON_TEAM = {
    "sport": "nhl",
    "season": "2024",
    "game_key": "453",
    "league_id": "12345",
    "team_id": "1",
    "team_name": "Old Season Team",
    "is_active": False,
}


class TestSingleActiveTeamAutoOnboards:
    @patch("agent.context_validator.onboard_user_team")
    @patch("agent.context_validator._fetch_hockey_teams")
    def test_one_active_one_offseason_auto_onboards_active(
        self, mock_fetch, mock_onboard
    ):
        mock_fetch.return_value = [OFFSEASON_TEAM, ACTIVE_TEAM]
        mock_onboard.invoke.return_value = "Successfully saved your team 'Steamys Dumps'!"

        result = _handle_no_teams_in_db("user@example.com")

        mock_onboard.invoke.assert_called_once_with(
            {
                "user_email": "user@example.com",
                "game_key": "465",
                "league_id": 26455,
                "team_name": "Steamys Dumps",
                "team_id": 9,
            }
        )
        assert result.league_id == "26455"
        assert result.team_id == "9"
        assert "AUTO-ONBOARDED" in result.system_message

    @patch("agent.context_validator.onboard_user_team")
    @patch("agent.context_validator._fetch_hockey_teams")
    def test_single_active_team_only(self, mock_fetch, mock_onboard):
        mock_fetch.return_value = [ACTIVE_TEAM]
        mock_onboard.invoke.return_value = "Success"

        result = _handle_no_teams_in_db("user@example.com")

        mock_onboard.invoke.assert_called_once()
        assert result.league_id == "26455"
        assert result.team_id == "9"


class TestMultipleActiveTeamsStillAsks:
    @patch("agent.context_validator._fetch_hockey_teams")
    def test_two_active_teams_prompts_selection(self, mock_fetch):
        second_active = {**ACTIVE_TEAM, "league_id": "99999", "team_name": "Other Team"}
        mock_fetch.return_value = [ACTIVE_TEAM, second_active]

        result = _handle_no_teams_in_db("user@example.com")

        assert "SELECT TEAM TO ONBOARD" in result.system_message
        assert result.league_id is None
        assert result.team_id is None


class TestNoActiveTeamsStillAsks:
    @patch("agent.context_validator._fetch_hockey_teams")
    def test_only_offseason_teams_prompts_selection(self, mock_fetch):
        mock_fetch.return_value = [OFFSEASON_TEAM]

        result = _handle_no_teams_in_db("user@example.com")

        assert "SELECT TEAM TO ONBOARD" in result.system_message
        assert result.league_id is None

    @patch("agent.context_validator._fetch_hockey_teams")
    def test_no_teams_at_all(self, mock_fetch):
        mock_fetch.return_value = []

        result = _handle_no_teams_in_db("user@example.com")

        assert "NO HOCKEY TEAMS AVAILABLE" in result.system_message
