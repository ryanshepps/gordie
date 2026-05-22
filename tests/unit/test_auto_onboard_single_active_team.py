from unittest.mock import patch

from agent.context_node import _handle_no_teams

ACTIVE_TEAM = {
    "sport": "nhl",
    "season": "2025",
    "game_key": "465",
    "league_id": "26455",
    "team_id": "9",
    "team_name": "Steamys Dumps",
    "is_active": True,
}

ACTIVE_MLB_TEAM = {
    "sport": "mlb",
    "season": "2025",
    "game_key": "449",
    "league_id": "77777",
    "team_id": "3",
    "team_name": "Dingerz",
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
    @patch("agent.context_node.auto_onboard_team")
    @patch("agent.context_node.fetch_supported_teams")
    def test_one_active_one_offseason_auto_onboards_active(self, mock_fetch, mock_onboard):
        mock_fetch.return_value = [OFFSEASON_TEAM, ACTIVE_TEAM]
        mock_onboard.return_value = ACTIVE_TEAM

        result = _handle_no_teams("user@example.com")

        mock_onboard.assert_called_once_with("user@example.com", ACTIVE_TEAM)
        assert result.get("league_id") == "26455"
        assert result.get("team_id") == "9"
        assert result["context_status"] == "auto_onboarded"

    @patch("agent.context_node.auto_onboard_team")
    @patch("agent.context_node.fetch_supported_teams")
    def test_single_active_team_only(self, mock_fetch, mock_onboard):
        mock_fetch.return_value = [ACTIVE_TEAM]
        mock_onboard.return_value = ACTIVE_TEAM

        result = _handle_no_teams("user@example.com")

        mock_onboard.assert_called_once()
        assert result.get("league_id") == "26455"
        assert result.get("team_id") == "9"

    @patch("agent.context_node.auto_onboard_team")
    @patch("agent.context_node.fetch_supported_teams")
    def test_single_active_mlb_team_auto_onboards_with_correct_sport(
        self, mock_fetch, mock_onboard
    ):
        mock_fetch.return_value = [ACTIVE_MLB_TEAM]
        mock_onboard.return_value = ACTIVE_MLB_TEAM

        result = _handle_no_teams("user@example.com")

        mock_onboard.assert_called_once_with("user@example.com", ACTIVE_MLB_TEAM)
        assert result.get("league_id") == "77777"
        assert result.get("sport") == "mlb"
        assert result["context_status"] == "auto_onboarded"


class TestMultipleActiveTeamsStillAsks:
    @patch("agent.context_node.fetch_supported_teams")
    def test_two_active_teams_prompts_selection(self, mock_fetch):
        second_active = {**ACTIVE_TEAM, "league_id": "99999", "team_name": "Other Team"}
        mock_fetch.return_value = [ACTIVE_TEAM, second_active]

        result = _handle_no_teams("user@example.com")

        assert result["context_status"] == "team_selection_needed"
        assert result.get("league_id") is None

    @patch("agent.context_node.fetch_supported_teams")
    def test_cross_sport_active_teams_prompts_selection(self, mock_fetch):
        mock_fetch.return_value = [ACTIVE_TEAM, ACTIVE_MLB_TEAM]

        result = _handle_no_teams("user@example.com")

        assert result["context_status"] == "team_selection_needed"
        assert result.get("league_id") is None


class TestNoActiveTeamsStillAsks:
    @patch("agent.context_node.fetch_supported_teams")
    def test_only_offseason_teams_prompts_selection(self, mock_fetch):
        mock_fetch.return_value = [OFFSEASON_TEAM]

        result = _handle_no_teams("user@example.com")

        assert result["context_status"] == "team_selection_needed"
        assert result.get("league_id") is None

    @patch("agent.context_node.fetch_supported_teams")
    def test_no_teams_at_all(self, mock_fetch):
        mock_fetch.return_value = []

        result = _handle_no_teams("user@example.com")

        assert result["context_status"] == "no_teams_available"
