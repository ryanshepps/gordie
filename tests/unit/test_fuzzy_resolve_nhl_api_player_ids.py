"""Tests for fuzzy_resolve_nhl_api_player_ids tool.

MoneyPuck CLI and NHL API calls are mocked.
"""

import json
from unittest.mock import Mock, patch

import pytest

from tools.hockey.player.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)

MOCK_PLAYERS = [
    {"player_id": 8478402, "name": "Connor McDavid", "team": "EDM", "position": "C", "games_played": 67},
    {"player_id": 8477934, "name": "Leon Draisaitl", "team": "EDM", "position": "C", "games_played": 65},
    {"player_id": 8480069, "name": "Cale Makar", "team": "COL", "position": "D", "games_played": 60},
]


def _mock_search(query: str) -> list[dict[str, str | int]]:
    return [p for p in MOCK_PLAYERS if query.lower() in str(p["name"]).lower()]


@pytest.fixture
def mock_moneypuck_search():
    with patch(
        "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.moneypuck_search_cli",
        side_effect=_mock_search,
    ):
        yield


class TestMoneyPuckLookup:

    def test_finds_player_by_full_name(self, mock_moneypuck_search):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Connor McDavid"]))

        assert "Connor McDavid" in result
        player_result = result["Connor McDavid"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "moneypuck"
        assert player_result["player_id"] == 8478402

    def test_finds_player_by_last_name(self, mock_moneypuck_search):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"]))

        assert "McDavid" in result
        player_result = result["McDavid"]
        assert player_result["status"] == "success"
        assert player_result["player_id"] == 8478402

    def test_finds_player_by_partial_name(self, mock_moneypuck_search):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Draisaitl"]))

        assert "Draisaitl" in result
        player_result = result["Draisaitl"]
        assert player_result["status"] == "success"
        assert player_result["player_id"] == 8477934

    def test_resolves_multiple_players(self, mock_moneypuck_search):
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid", "Draisaitl", "Makar"])
        )

        assert len(result) == 3
        assert result["McDavid"]["player_id"] == 8478402
        assert result["Draisaitl"]["player_id"] == 8477934
        assert result["Makar"]["player_id"] == 8480069

    def test_includes_games_played_count(self, mock_moneypuck_search):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"]))

        player_result = result["McDavid"]
        assert player_result["games_in_db"] == 67


class TestNHLAPIFallback:

    @pytest.fixture
    def mock_empty_moneypuck(self):
        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.moneypuck_search_cli",
            return_value=[],
        ):
            yield

    def test_falls_back_to_nhl_api_when_not_in_moneypuck(self, mock_empty_moneypuck):
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "playerId": 8471214,
                "name": "Sidney Crosby",
                "teamAbbrev": "PIT",
                "positionCode": "C",
                "active": True,
            }
        ]
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

            mock_get.assert_called_once()

        player_result = result["Crosby"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "nhl_api"
        assert player_result["player_id"] == 8471214

    def test_nhl_api_result_includes_warning_message(self, mock_empty_moneypuck):
        mock_response = Mock()
        mock_response.json.return_value = [
            {"playerId": 8471214, "name": "Sidney Crosby", "active": True}
        ]
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ):
            result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

        assert "message" in result["Crosby"]
        assert "NHL API" in result["Crosby"]["message"]

    def test_does_not_call_api_when_found_in_moneypuck(self, mock_moneypuck_search):
        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.requests.get"
        ) as mock_get:
            fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"])
            mock_get.assert_not_called()

    def test_returns_not_found_when_api_returns_empty(self, mock_empty_moneypuck):
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids(player_names=["NonexistentPlayer"])
            )

        assert result["NonexistentPlayer"]["status"] == "not_found"

    def test_handles_api_error_gracefully(self, mock_empty_moneypuck):
        import requests

        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.requests.get",
            side_effect=requests.RequestException("API Error"),
        ):
            result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["UnknownPlayer"]))

        assert result["UnknownPlayer"]["status"] == "error"


class TestMultipleMatches:

    @pytest.fixture
    def mock_moneypuck_with_similar_names(self):
        similar_players = [
            {"player_id": 8471675, "name": "Sidney Crosby", "team": "PIT", "position": "C", "games_played": 70},
            {"player_id": 8471677, "name": "Mike Crosby", "team": "BOS", "position": "R", "games_played": 30},
        ]

        def search_func(query: str) -> list[dict[str, str | int]]:
            return [p for p in similar_players if query.lower() in str(p["name"]).lower()]

        with patch(
            "tools.hockey.player.fuzzy_resolve_nhl_api_player_ids.moneypuck_search_cli",
            side_effect=search_func,
        ):
            yield

    def test_returns_multiple_matches_when_ambiguous(self, mock_moneypuck_with_similar_names):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

        player_result = result["Crosby"]
        assert player_result["status"] == "multiple_matches"
        assert "matches" in player_result
        assert len(player_result["matches"]) == 2

    def test_multiple_matches_include_player_details(self, mock_moneypuck_with_similar_names):
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

        matches = result["Crosby"]["matches"]
        for match in matches:
            assert "player_id" in match
            assert "full_name" in match
