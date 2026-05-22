"""Tests for Yahoo stats tool method dispatch, validation, and param unpacking."""

import json
from unittest.mock import MagicMock, patch


def _make_mock_client() -> MagicMock:
    mock_client = MagicMock()
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    return mock_client


class TestYahooScoringDispatch:
    @patch("tools.yahoo_stats.yahoo_scoring.AuthenticatedYahooClient")
    def test_invalid_method_returns_error(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

        result = yahoo_scoring.invoke(
            {"user_email": "test@test.com", "league_id": "123", "method": "bad_method"}
        )
        parsed = json.loads(result)
        assert "error" in parsed
        assert "bad_method" in parsed["error"]
        mock_cls.assert_not_called()

    @patch("tools.yahoo_stats.yahoo_scoring.AuthenticatedYahooClient")
    def test_get_league_standings(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        team = MagicMock()
        team.team_id = "1"
        team.team_key = "nhl.l.123.t.1"
        team.name = "Team A"
        team.waiver_priority = 1
        team.number_of_moves = 5
        team.number_of_trades = 1
        team.team_standings = None
        team.managers = []

        mock_instance.query.get_league_standings.return_value = [team]

        result = yahoo_scoring.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_standings",
            }
        )
        parsed = json.loads(result)

        assert "standings" in parsed
        assert len(parsed["standings"]) == 1
        assert parsed["standings"][0]["team_id"] == "1"

    @patch("tools.yahoo_stats.yahoo_scoring.AuthenticatedYahooClient")
    def test_get_league_scoreboard_by_week(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        team1 = MagicMock()
        team1.team_key = "nhl.l.123.t.1"
        team1.name = "Team A"
        team1_points = MagicMock()
        team1_points.total = 85.5
        team1.team_points = team1_points
        team1.team_projected_points = None

        team2 = MagicMock()
        team2.team_key = "nhl.l.123.t.2"
        team2.name = "Team B"
        team2_points = MagicMock()
        team2_points.total = 72.0
        team2.team_points = team2_points
        team2.team_projected_points = None

        matchup = MagicMock()
        matchup.week = 5
        matchup.status = "postevent"
        matchup.winner_team_key = "nhl.l.123.t.1"
        matchup.teams = [team1, team2]

        scoreboard = MagicMock()
        scoreboard.matchups = [matchup]
        scoreboard.week = 5

        mock_instance.query.get_league_scoreboard_by_week.return_value = scoreboard

        result = yahoo_scoring.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_scoreboard_by_week",
                "params_json": json.dumps({"week": 5}),
            }
        )
        parsed = json.loads(result)

        assert "matchups" in parsed
        assert parsed["week"] == 5
        assert len(parsed["matchups"]) == 1
        assert len(parsed["matchups"][0]["teams"]) == 2
        assert parsed["matchups"][0]["teams"][0]["points"] == 85.5


class TestYahooRosterDispatch:
    @patch("tools.yahoo_stats.yahoo_roster.AuthenticatedYahooClient")
    def test_invalid_method_returns_error(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_roster import yahoo_roster

        result = yahoo_roster.invoke(
            {"user_email": "test@test.com", "league_id": "123", "method": "nonexistent"}
        )
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("tools.yahoo_stats.yahoo_roster.AuthenticatedYahooClient")
    def test_get_team_roster_player_stats(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_roster import yahoo_roster

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        player = MagicMock()
        name_obj = MagicMock()
        name_obj.full = "Leon Draisaitl"
        player.name = name_obj
        player.player_key = "nhl.p.5017"
        player.player_id = "5017"
        player.display_position = "C"
        player.editorial_team_abbr = "EDM"
        player.editorial_team_full_name = "Edmonton Oilers"
        player.status = None
        player.status_full = None
        player_stats = MagicMock()
        player_stats.total_points = 45
        player_stats.stats = []
        player.player_stats = player_stats
        player.player_points = None

        mock_instance.query.get_team_roster_player_stats.return_value = [player]

        result = yahoo_roster.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_team_roster_player_stats",
                "params_json": json.dumps({"team_id": "1"}),
            }
        )
        parsed = json.loads(result)

        assert "players" in parsed
        assert parsed["count"] == 1
        assert parsed["players"][0]["name"] == "Leon Draisaitl"
        assert parsed["players"][0]["fantasy_points"] == 45


class TestYahooPlayerDispatch:
    @patch("tools.yahoo_stats.yahoo_player.AuthenticatedYahooClient")
    def test_invalid_method_returns_error(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_player import yahoo_player

        result = yahoo_player.invoke(
            {"user_email": "test@test.com", "league_id": "123", "method": "fake"}
        )
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("tools.yahoo_stats.yahoo_player.AuthenticatedYahooClient")
    def test_get_player_stats_for_season(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_player import yahoo_player

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        player = MagicMock()
        name_obj = MagicMock()
        name_obj.full = "Auston Matthews"
        player.name = name_obj
        player.player_key = "nhl.p.7890"
        player.player_id = "7890"
        player.display_position = "C"
        player.editorial_team_abbr = "TOR"
        player.editorial_team_full_name = "Toronto Maple Leafs"
        player.status = None
        player.status_full = None
        player.player_stats = None
        player.player_points = None

        mock_instance.query.get_player_stats_for_season.return_value = player

        result = yahoo_player.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_player_stats_for_season",
                "params_json": json.dumps({"player_key": "nhl.p.7890"}),
            }
        )
        parsed = json.loads(result)

        assert "player" in parsed
        assert parsed["player"]["name"] == "Auston Matthews"


class TestYahooLeagueDispatch:
    @patch("tools.yahoo_stats.yahoo_league.AuthenticatedYahooClient")
    def test_invalid_method_returns_error(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_league import yahoo_league

        result = yahoo_league.invoke(
            {"user_email": "test@test.com", "league_id": "123", "method": "nope"}
        )
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("tools.yahoo_stats.yahoo_league.AuthenticatedYahooClient")
    def test_get_league_teams(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_league import yahoo_league

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        team = MagicMock()
        team.team_id = "1"
        team.team_key = "nhl.l.123.t.1"
        team.name = "My Team"
        team.waiver_priority = 1
        team.number_of_moves = 3
        team.number_of_trades = 0
        team.team_standings = None
        team.managers = []

        mock_instance.query.get_league_teams.return_value = [team]

        result = yahoo_league.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_teams",
            }
        )
        parsed = json.loads(result)

        assert "teams" in parsed
        assert len(parsed["teams"]) == 1

    @patch("tools.yahoo_stats.yahoo_league.AuthenticatedYahooClient")
    def test_get_league_info(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_league import yahoo_league

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        league_info = MagicMock()
        league_info.current_week = 15
        league_info.start_date = "2024-10-07"
        league_info.end_date = "2025-04-13"
        mock_instance.query.get_league_info.return_value = league_info

        result = yahoo_league.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_info",
            }
        )
        parsed = json.loads(result)

        assert "league_info" in parsed

    @patch("tools.yahoo_stats.yahoo_league.AuthenticatedYahooClient")
    def test_get_league_draft_results(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_league import yahoo_league

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        pick = MagicMock()
        pick.pick = 1
        pick.round = 1
        pick.team_key = "nhl.l.123.t.1"
        pick.player_key = "nhl.p.6743"
        mock_instance.query.get_league_draft_results.return_value = [pick]

        result = yahoo_league.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_draft_results",
            }
        )
        parsed = json.loads(result)

        assert "draft_results" in parsed
        assert parsed["draft_results"][0]["pick"] == 1


class TestParamsJsonParsing:
    @patch("tools.yahoo_stats.yahoo_scoring.AuthenticatedYahooClient")
    def test_default_empty_params(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.query.get_league_standings.return_value = []

        result = yahoo_scoring.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_standings",
            }
        )
        parsed = json.loads(result)

        assert "standings" in parsed

    @patch("tools.yahoo_stats.yahoo_scoring.AuthenticatedYahooClient")
    def test_api_error_returns_json(self, mock_cls: MagicMock) -> None:
        from tools.yahoo_stats.yahoo_scoring import yahoo_scoring

        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.query.get_league_standings.side_effect = RuntimeError("API down")

        result = yahoo_scoring.invoke(
            {
                "user_email": "test@test.com",
                "league_id": "123",
                "method": "get_league_standings",
            }
        )
        parsed = json.loads(result)

        assert "error" in parsed
        assert "API down" in parsed["error"]
