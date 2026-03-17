"""Tests for yfpy object serialization."""

from unittest.mock import MagicMock

from tools.yahoo_stats.serializer import (
    serialize_draft_pick,
    serialize_generic,
    serialize_matchup,
    serialize_player,
    serialize_team,
    serialize_transaction,
)


class TestSerializePlayer:
    def test_basic_player(self) -> None:
        player = MagicMock()
        name_obj = MagicMock()
        name_obj.full = "Connor McDavid"
        player.name = name_obj
        player.player_key = "nhl.p.6743"
        player.player_id = "6743"
        player.display_position = "C"
        player.editorial_team_abbr = "EDM"
        player.editorial_team_full_name = "Edmonton Oilers"
        player.status = None
        player.status_full = None
        player.player_stats = None
        player.player_points = None

        result = serialize_player(player)

        assert result["name"] == "Connor McDavid"
        assert result["player_key"] == "nhl.p.6743"
        assert result["position"] == "C"
        assert result["nhl_team"] == "EDM"
        assert result["fantasy_points"] is None

    def test_player_with_stats(self) -> None:
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
        player_stats.total_points = 45.5
        stat1 = MagicMock()
        stat1.stat_id = "1"
        stat1.value = "20"
        stat2 = MagicMock()
        stat2.stat_id = "2"
        stat2.value = "25"
        player_stats.stats = [stat1, stat2]
        player.player_stats = player_stats
        player.player_points = None

        result = serialize_player(player)

        assert result["fantasy_points"] == 45.5
        stats = result["stats"]
        assert isinstance(stats, list)
        assert len(stats) == 2
        assert stats[0]["stat_id"] == "1"

    def test_player_with_bytes_name(self) -> None:
        player = MagicMock()
        name_obj = MagicMock()
        name_obj.full = b"Mikko R\xc3\xa4nt\xc3\xa4nen"
        player.name = name_obj
        player.player_key = "nhl.p.1234"
        player.player_id = "1234"
        player.display_position = "RW"
        player.editorial_team_abbr = "COL"
        player.editorial_team_full_name = "Colorado Avalanche"
        player.status = None
        player.status_full = None
        player.player_stats = None
        player.player_points = None

        result = serialize_player(player)

        assert isinstance(result["name"], str)
        assert "nt" in result["name"]

    def test_player_missing_name(self) -> None:
        player = MagicMock()
        player.name = None
        player.player_key = "nhl.p.9999"
        player.player_id = "9999"
        player.display_position = "D"
        player.editorial_team_abbr = "TOR"
        player.editorial_team_full_name = "Toronto Maple Leafs"
        player.status = None
        player.status_full = None
        player.player_stats = None
        player.player_points = None

        result = serialize_player(player)

        assert result["name"] == "Unknown"


class TestSerializeTeam:
    def test_team_with_standings(self) -> None:
        team = MagicMock()
        team.team_id = "1"
        team.team_key = "nhl.l.12345.t.1"
        team.name = "Test Team"
        team.waiver_priority = 3
        team.number_of_moves = 10
        team.number_of_trades = 2

        standings = MagicMock()
        standings.wins = 15
        standings.losses = 8
        standings.ties = 2
        standings.points_for = 1250.5
        standings.points_against = 1180.0
        standings.rank = 2
        team.team_standings = standings

        manager = MagicMock()
        manager.nickname = "TestManager"
        team.managers = [manager]

        result = serialize_team(team)

        assert result["team_id"] == "1"
        assert result["name"] == "Test Team"
        assert result["wins"] == 15
        assert result["losses"] == 8
        assert result["rank"] == 2
        assert result["manager"] == "TestManager"

    def test_team_without_standings(self) -> None:
        team = MagicMock()
        team.team_id = "2"
        team.team_key = "nhl.l.12345.t.2"
        team.name = "Other Team"
        team.waiver_priority = 1
        team.number_of_moves = 5
        team.number_of_trades = 0
        team.team_standings = None
        team.managers = []

        result = serialize_team(team)

        assert result["wins"] is None
        assert result["manager"] is None


class TestSerializeMatchup:
    def test_matchup_with_teams(self) -> None:
        matchup = MagicMock()
        matchup.week = 10
        matchup.status = "postevent"
        matchup.winner_team_key = "nhl.l.12345.t.1"

        team1 = MagicMock()
        team1.team_key = "nhl.l.12345.t.1"
        team1.name = "Team A"
        team1_points = MagicMock()
        team1_points.total = 85.5
        team1.team_points = team1_points
        team1.team_projected_points = None

        team2 = MagicMock()
        team2.team_key = "nhl.l.12345.t.2"
        team2.name = "Team B"
        team2_points = MagicMock()
        team2_points.total = 72.0
        team2.team_points = team2_points
        team2.team_projected_points = None

        matchup.teams = [team1, team2]

        result = serialize_matchup(matchup)

        assert result["week"] == 10
        teams = result["teams"]
        assert isinstance(teams, list)
        assert len(teams) == 2
        assert teams[0]["points"] == 85.5


class TestSerializeDraftPick:
    def test_draft_pick(self) -> None:
        pick = MagicMock()
        pick.pick = 1
        pick.round = 1
        pick.team_key = "nhl.l.12345.t.1"
        pick.player_key = "nhl.p.6743"

        result = serialize_draft_pick(pick)

        assert result["pick"] == 1
        assert result["round"] == 1
        assert result["player_key"] == "nhl.p.6743"


class TestSerializeTransaction:
    def test_transaction(self) -> None:
        tx = MagicMock()
        tx.transaction_key = "tx_123"
        tx.type = "add/drop"
        tx.timestamp = "1700000000"
        tx.status = "successful"

        p1 = MagicMock()
        p1.player_key = "nhl.p.1234"
        p1_name = MagicMock()
        p1_name.full = "Player One"
        p1.name = p1_name
        p1.transaction_data = "add"

        tx.players = [p1]

        result = serialize_transaction(tx)

        assert result["type"] == "add/drop"
        players = result["players"]
        assert isinstance(players, list)
        assert len(players) == 1
        assert players[0]["player_key"] == "nhl.p.1234"


class TestSerializeGeneric:
    def test_primitives(self) -> None:
        assert serialize_generic(42) == 42
        assert serialize_generic("hello") == "hello"
        assert serialize_generic(None) is None

    def test_bytes(self) -> None:
        result = serialize_generic(b"test bytes")
        assert result == "test bytes"

    def test_list(self) -> None:
        result = serialize_generic([1, "two", 3.0])
        assert result == [1, "two", 3.0]

    def test_dict(self) -> None:
        result = serialize_generic({"key": "value", "num": 42})
        assert result == {"key": "value", "num": 42}

    def test_object_with_attrs(self) -> None:
        obj = MagicMock()
        obj.configure_mock(**{"__dir__": lambda s: ["name", "value", "_private"]})
        obj.name = "test"
        obj.value = 42
        result = serialize_generic(obj)
        assert isinstance(result, dict)
