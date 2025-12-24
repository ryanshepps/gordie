"""Tests for fuzzy_resolve_nhl_api_player_ids tool.

These tests verify the behavior of resolving player names to NHL API player IDs.
Tests focus on outcomes users care about:
- Finding players via MoneyPuck data
- Falling back to NHL API when not found in MoneyPuck
- Handling multiple matches and edge cases

MoneyPuck and NHL API calls are mocked.
"""

import json
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)


@pytest.fixture
def mock_moneypuck_data():
    """Create mock MoneyPuck DataFrame with test players."""
    return pd.DataFrame(
        [
            {
                "playerId": 8478402,
                "name": "Connor McDavid",
                "team": "EDM",
                "position": "C",
                "games_played": 67,
            },
            {
                "playerId": 8477934,
                "name": "Leon Draisaitl",
                "team": "EDM",
                "position": "C",
                "games_played": 65,
            },
            {
                "playerId": 8480069,
                "name": "Cale Makar",
                "team": "COL",
                "position": "D",
                "games_played": 60,
            },
        ]
    )


@pytest.fixture
def mock_moneypuck_search(mock_moneypuck_data):
    """Mock the MoneyPuck search function."""

    def search_func(query, situation="all", limit=5):
        df = mock_moneypuck_data
        matches = df[df["name"].str.lower().str.contains(query.lower(), na=False)]
        return matches.head(limit)

    with patch(
        "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.moneypuck_search",
        side_effect=search_func,
    ):
        yield


class TestMoneyPuckLookup:
    """Test that players are found via MoneyPuck."""

    def test_finds_player_by_full_name(self, mock_moneypuck_search):
        """Player found by full name returns success with moneypuck source."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids(player_names=["Connor McDavid"])
        )

        assert "Connor McDavid" in result
        player_result = result["Connor McDavid"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "moneypuck"
        assert player_result["player_id"] == 8478402
        assert player_result["full_name"] == "Connor McDavid"

    def test_finds_player_by_last_name(self, mock_moneypuck_search):
        """Player found by last name only returns success."""
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"]))

        assert "McDavid" in result
        player_result = result["McDavid"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "moneypuck"
        assert player_result["player_id"] == 8478402

    def test_finds_player_by_partial_name(self, mock_moneypuck_search):
        """Player found by partial name match returns success."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids(player_names=["Draisaitl"])
        )

        assert "Draisaitl" in result
        player_result = result["Draisaitl"]
        assert player_result["status"] == "success"
        assert player_result["player_id"] == 8477934

    def test_resolves_multiple_players(self, mock_moneypuck_search):
        """Multiple player names are resolved in a single call."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids(
                player_names=["McDavid", "Draisaitl", "Makar"]
            )
        )

        assert len(result) == 3
        assert result["McDavid"]["player_id"] == 8478402
        assert result["Draisaitl"]["player_id"] == 8477934
        assert result["Makar"]["player_id"] == 8480069

    def test_includes_games_played_count(self, mock_moneypuck_search):
        """Result includes games played from MoneyPuck data."""
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"]))

        player_result = result["McDavid"]
        assert player_result["games_in_db"] == 67


class TestNHLAPIFallback:
    """Test fallback to NHL API when player not found in MoneyPuck."""

    @pytest.fixture
    def mock_empty_moneypuck(self):
        """Mock MoneyPuck to return empty results."""
        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.moneypuck_search",
            return_value=pd.DataFrame(),
        ):
            yield

    def test_falls_back_to_nhl_api_when_not_in_moneypuck(self, mock_empty_moneypuck):
        """Player not in MoneyPuck is searched via NHL API."""
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
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"])
            )

            # Verify NHL API was called
            mock_get.assert_called_once()
            assert "Crosby" in mock_get.call_args[0][0]

        assert "Crosby" in result
        player_result = result["Crosby"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "nhl_api"
        assert player_result["player_id"] == 8471214
        assert player_result["full_name"] == "Sidney Crosby"
        assert player_result["team_abbrev"] == "PIT"
        assert player_result["position"] == "C"
        assert player_result["active"] is True

    def test_nhl_api_result_includes_warning_message(self, mock_empty_moneypuck):
        """NHL API results include message about stats not being available locally."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"playerId": 8471214, "name": "Sidney Crosby", "active": True}
        ]
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"])
            )

        assert "message" in result["Crosby"]
        assert "NHL API" in result["Crosby"]["message"]

    def test_does_not_call_api_when_found_in_moneypuck(self, mock_moneypuck_search):
        """NHL API is not called when player is found in MoneyPuck."""
        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get"
        ) as mock_get:
            fuzzy_resolve_nhl_api_player_ids(player_names=["McDavid"])
            mock_get.assert_not_called()

    def test_returns_not_found_when_api_returns_empty(self, mock_empty_moneypuck):
        """Returns not_found status when player not in MoneyPuck or API."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response,
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids(player_names=["NonexistentPlayer"])
            )

        player_result = result["NonexistentPlayer"]
        assert player_result["status"] == "not_found"

    def test_handles_api_error_gracefully(self, mock_empty_moneypuck):
        """API errors result in error status, not exceptions."""
        import requests

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            side_effect=requests.RequestException("API Error"),
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids(player_names=["UnknownPlayer"])
            )

        player_result = result["UnknownPlayer"]
        assert player_result["status"] == "error"


class TestMultipleMatches:
    """Test handling of ambiguous searches with multiple matches."""

    @pytest.fixture
    def mock_moneypuck_with_similar_names(self):
        """Mock MoneyPuck with players having similar names."""
        similar_players = pd.DataFrame(
            [
                {
                    "playerId": 8471675,
                    "name": "Sidney Crosby",
                    "team": "PIT",
                    "position": "C",
                    "games_played": 70,
                },
                {
                    "playerId": 8471677,
                    "name": "Mike Crosby",
                    "team": "BOS",
                    "position": "R",
                    "games_played": 30,
                },
            ]
        )

        def search_func(query, situation="all", limit=5):
            name_col = similar_players["name"].str.lower()
            matches = similar_players[name_col.str.contains(query.lower(), na=False)]
            return matches.head(limit)

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.moneypuck_search",
            side_effect=search_func,
        ):
            yield

    def test_returns_multiple_matches_when_ambiguous(self, mock_moneypuck_with_similar_names):
        """Ambiguous search returns multiple_matches status with all options."""
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

        player_result = result["Crosby"]
        assert player_result["status"] == "multiple_matches"
        assert "matches" in player_result
        assert len(player_result["matches"]) == 2  # Sidney Crosby and Mike Crosby

    def test_multiple_matches_include_player_details(self, mock_moneypuck_with_similar_names):
        """Each match in multiple_matches includes player details."""
        result = json.loads(fuzzy_resolve_nhl_api_player_ids(player_names=["Crosby"]))

        matches = result["Crosby"]["matches"]
        for match in matches:
            assert "player_id" in match
            assert "full_name" in match
