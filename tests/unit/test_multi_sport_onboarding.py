from unittest.mock import patch

from agent.context_resolvers import auto_onboard_team, format_teams_for_display

NHL_TEAM: dict[str, str] = {
    "sport": "nhl",
    "season": "2025",
    "game_key": "465",
    "league_id": "26455",
    "team_id": "9",
    "team_name": "Steamys Dumps",
}

MLB_TEAM: dict[str, str] = {
    "sport": "mlb",
    "season": "2025",
    "game_key": "449",
    "league_id": "77777",
    "team_id": "3",
    "team_name": "Dingerz",
}


class TestAutoOnboardTeamPassesGameCode:
    @patch("agent.context_resolvers.onboard_user_team")
    def test_nhl_team_passes_nhl_game_code(self, mock_onboard):
        mock_onboard.invoke.return_value = "Success"

        auto_onboard_team("user@example.com", NHL_TEAM)

        call_args = mock_onboard.invoke.call_args[0][0]
        assert call_args["game_code"] == "nhl"

    @patch("agent.context_resolvers.onboard_user_team")
    def test_mlb_team_passes_mlb_game_code(self, mock_onboard):
        mock_onboard.invoke.return_value = "Success"

        auto_onboard_team("user@example.com", MLB_TEAM)

        call_args = mock_onboard.invoke.call_args[0][0]
        assert call_args["game_code"] == "mlb"

    @patch("agent.context_resolvers.onboard_user_team")
    def test_missing_sport_defaults_to_nhl(self, mock_onboard):
        mock_onboard.invoke.return_value = "Success"
        team_no_sport: dict[str, str] = {
            "game_key": "465",
            "league_id": "26455",
            "team_id": "9",
            "team_name": "Legacy Team",
        }

        auto_onboard_team("user@example.com", team_no_sport)

        call_args = mock_onboard.invoke.call_args[0][0]
        assert call_args["game_code"] == "nhl"


class TestFormatTeamsForDisplay:
    def test_shows_sport_label(self):
        teams: list[dict[str, str]] = [
            {"sport": "nhl", "team_name": "Steamys", "season": "2025", "game_key": "465", "league_id": "1", "team_id": "1"},
        ]

        result = format_teams_for_display(teams)

        assert "[NHL]" in result

    def test_shows_multiple_sport_labels(self):
        teams: list[dict[str, str]] = [
            {"sport": "nhl", "team_name": "Steamys", "season": "2025", "game_key": "465", "league_id": "1", "team_id": "1"},
            {"sport": "mlb", "team_name": "Dingerz", "season": "2025", "game_key": "449", "league_id": "2", "team_id": "2"},
        ]

        result = format_teams_for_display(teams)

        assert "[NHL]" in result
        assert "[MLB]" in result
