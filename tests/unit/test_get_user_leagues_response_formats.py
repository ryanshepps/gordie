"""Unit tests for get_user_leagues tool.

These tests verify the tool correctly handles different Yahoo API response formats.
Each test represents a distinct user scenario - only one should fail per regression.
"""

from unittest.mock import MagicMock, patch

from yfpy.exceptions import YahooFantasySportsDataNotFound

from tools.yahoo.get_user_leagues import get_user_leagues

USER_STATE = {"state": {"user_id": "00000000-0000-0000-0000-000000000001"}}


class MockGame:
    """Mock Game object for testing."""

    def __init__(self, game_id, code, season, teams, is_offseason=False):
        self.game_id = game_id
        self.code = code
        self.season = season
        self.teams = teams
        self.is_offseason = is_offseason


class MockTeam:
    """Mock Team object for testing."""

    def __init__(self, team_key, name):
        self.team_key = team_key
        self.name = name


def _create_mock_client(mock_query):
    """Helper to create mock AuthenticatedYahooClient."""
    mock_client = MagicMock()
    mock_client.query = mock_query
    return mock_client


class TestUserWithSingleTeam:
    """Test user with exactly one team."""

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_single_team_user(self, mock_client_class):
        """User with one team in one game should have team extracted correctly.

        This was the original bug: yfpy returns {'game': Game} for single game
        and {'team': Team} for single team, which caused iteration errors.
        """
        team = MockTeam("465.l.26455.t.9", "All-Star Beet")
        game = MockGame(465, "nhl", 2025, {"team": team}, is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = {"game": game}
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert len(teams_list) == 1
        assert teams_list[0]["team_name"] == "All-Star Beet"
        assert teams_list[0]["league_id"] == "26455"
        assert teams_list[0]["team_id"] == "9"
        assert teams_list[0]["sport"] == "nhl"
        assert teams_list[0]["is_active"] is True


class TestUserWithMultipleTeams:
    """Test user with multiple teams across different formats."""

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_multiple_teams_same_game(self, mock_client_class):
        """User with multiple teams in the same game."""
        team1 = MockTeam("465.l.26455.t.9", "Team A")
        team2 = MockTeam("465.l.26455.t.10", "Team B")
        game = MockGame(465, "nhl", 2025, [team1, team2], is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert len(teams_list) == 2
        assert teams_list[0]["team_name"] == "Team A"
        assert teams_list[1]["team_name"] == "Team B"

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_multiple_games_multiple_teams(self, mock_client_class):
        """User with teams across multiple games/seasons."""
        team1 = MockTeam("465.l.26455.t.9", "2025 Team")
        team2 = MockTeam("453.l.12345.t.1", "2024 Team")
        game1 = MockGame(465, "nhl", 2025, [team1], is_offseason=False)
        game2 = MockGame(453, "nhl", 2024, [team2], is_offseason=True)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game1, game2]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert len(teams_list) == 2
        assert teams_list[0]["season"] == 2025
        assert teams_list[0]["is_active"] is True
        assert teams_list[1]["season"] == 2024
        assert teams_list[1]["is_active"] is False


class TestUserWithNoTeams:
    """Test users who have no teams available."""

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_no_games_found(self, mock_client_class):
        """User authenticated but has no Yahoo Fantasy games at all."""
        mock_query = MagicMock()
        mock_query.get_user_teams.side_effect = YahooFantasySportsDataNotFound("No games")
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)

        assert result == "[]"

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_empty_games_list(self, mock_client_class):
        """User has games list but it's empty."""
        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = []
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert teams_list == []


class TestErrorHandling:
    """Test how the tool handles various error conditions."""

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_permission_error_in_teams(self, mock_client_class):
        """Yahoo returns error message in teams field due to permissions."""
        game = MockGame(465, "nhl", 2025, "Error: Permission denied", is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        # Should gracefully skip the error and return empty list
        assert teams_list == []

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_malformed_team_key(self, mock_client_class):
        """Team has malformed team_key that doesn't match expected format."""
        team = MockTeam("invalid-key-format", "Bad Team")
        game = MockGame(465, "nhl", 2025, [team], is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        # Should skip malformed team but not crash
        assert teams_list == []

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_team_missing_team_key(self, mock_client_class):
        """Team object is missing team_key attribute entirely."""
        team = MagicMock()
        team.name = "No Key Team"
        del team.team_key  # Explicitly remove team_key
        game = MockGame(465, "nhl", 2025, [team], is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        # Should skip team without team_key
        assert teams_list == []


class TestEdgeCases:
    """Test edge cases and unusual response formats."""

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_game_without_teams_attribute(self, mock_client_class):
        """Game object is missing teams attribute."""
        game = MagicMock()
        game.game_id = 465
        game.code = "nhl"
        game.season = 2025
        del game.teams  # No teams attribute

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert teams_list == []

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_offseason_team(self, mock_client_class):
        """Team in offseason should be marked as inactive."""
        team = MockTeam("465.l.26455.t.9", "Offseason Team")
        game = MockGame(465, "nhl", 2024, [team], is_offseason=True)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert len(teams_list) == 1
        assert teams_list[0]["is_active"] is False

    @patch("tools.yahoo.get_user_leagues.AuthenticatedYahooClient")
    def test_different_sport_code(self, mock_client_class):
        """Non-NHL sport should still work and report correct sport."""
        team = MockTeam("331.l.12345.t.1", "Football Team")
        game = MockGame(331, "nfl", 2025, [team], is_offseason=False)

        mock_query = MagicMock()
        mock_query.get_user_teams.return_value = [game]
        mock_client_class.return_value = _create_mock_client(mock_query)

        result = get_user_leagues.invoke(USER_STATE)
        teams_list = eval(result)

        assert len(teams_list) == 1
        assert teams_list[0]["sport"] == "nfl"
