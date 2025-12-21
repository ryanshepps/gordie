"""Tests for fuzzy_resolve_nhl_api_player_ids tool.

These tests verify the behavior of resolving player names to NHL API player IDs.
Tests focus on outcomes users care about:
- Finding players in the local database
- Falling back to NHL API when not found locally
- Handling multiple matches and edge cases

Only NHL API calls are mocked - the local database uses a real in-memory DuckDB.
"""

import json
from unittest.mock import Mock, patch

import duckdb
import pytest

from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)


@pytest.fixture
def db_connection():
    """Create an in-memory DuckDB database with test data."""
    conn = duckdb.connect(":memory:")

    # Create the table matching the schema expected by the tool
    conn.execute("""
        CREATE TABLE nhl_player_stats (
            nhl_api_player_id INTEGER,
            full_name VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            game_date DATE
        )
    """)

    # Insert test players
    test_players = [
        (8478402, "Connor McDavid", "Connor", "McDavid"),
        (8478402, "Connor McDavid", "Connor", "McDavid"),  # Multiple games
        (8478402, "Connor McDavid", "Connor", "McDavid"),
        (8477934, "Leon Draisaitl", "Leon", "Draisaitl"),
        (8477934, "Leon Draisaitl", "Leon", "Draisaitl"),
        (8480069, "Cale Makar", "Cale", "Makar"),
    ]

    for i, (player_id, full_name, first_name, last_name) in enumerate(test_players):
        conn.execute(
            "INSERT INTO nhl_player_stats VALUES (?, ?, ?, ?, ?)",
            [player_id, full_name, first_name, last_name, f"2024-01-{i+1:02d}"]
        )

    yield conn
    conn.close()


@pytest.fixture
def mock_repository(db_connection):
    """Mock the repository to use our test database."""
    mock_repo = Mock()
    mock_repo.conn = db_connection
    mock_repo.close = Mock()

    with patch(
        "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.NHLPlayerStatsRepository",
        return_value=mock_repo
    ):
        yield mock_repo


class TestLocalDatabaseLookup:
    """Test that players are found in the local database."""

    def test_finds_player_by_full_name(self, mock_repository):
        """Player found by full name returns success with local_database source."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Connor McDavid"]})
        )

        assert "Connor McDavid" in result
        player_result = result["Connor McDavid"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "local_database"
        assert player_result["player_id"] == 8478402
        assert player_result["full_name"] == "Connor McDavid"

    def test_finds_player_by_last_name(self, mock_repository):
        """Player found by last name only returns success."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["McDavid"]})
        )

        assert "McDavid" in result
        player_result = result["McDavid"]
        assert player_result["status"] == "success"
        assert player_result["source"] == "local_database"
        assert player_result["player_id"] == 8478402

    def test_finds_player_by_partial_name(self, mock_repository):
        """Player found by partial name match returns success."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Draisaitl"]})
        )

        assert "Draisaitl" in result
        player_result = result["Draisaitl"]
        assert player_result["status"] == "success"
        assert player_result["player_id"] == 8477934

    def test_resolves_multiple_players(self, mock_repository):
        """Multiple player names are resolved in a single call."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids.invoke(
                {"player_names": ["McDavid", "Draisaitl", "Makar"]}
            )
        )

        assert len(result) == 3
        assert result["McDavid"]["player_id"] == 8478402
        assert result["Draisaitl"]["player_id"] == 8477934
        assert result["Makar"]["player_id"] == 8480069

    def test_includes_games_in_db_count(self, mock_repository):
        """Result includes count of games in local database."""
        result = json.loads(
            fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["McDavid"]})
        )

        player_result = result["McDavid"]
        # McDavid has 3 games in our test data
        assert player_result["games_in_db"] == 3


class TestNHLAPIFallback:
    """Test fallback to NHL API when player not found locally."""

    def test_falls_back_to_nhl_api_when_not_in_database(self, mock_repository):
        """Player not in local DB is searched via NHL API."""
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
            return_value=mock_response
        ) as mock_get:
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Crosby"]})
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

    def test_nhl_api_result_includes_warning_message(self, mock_repository):
        """NHL API results include message about stats not being in local DB."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"playerId": 8471214, "name": "Sidney Crosby", "active": True}
        ]
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Crosby"]})
            )

        assert "message" in result["Crosby"]
        assert "NHL API" in result["Crosby"]["message"]

    def test_does_not_call_api_when_found_locally(self, mock_repository):
        """NHL API is not called when player is found in local database."""
        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get"
        ) as mock_get:
            fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["McDavid"]})
            mock_get.assert_not_called()

    def test_returns_not_found_when_api_returns_empty(self, mock_repository):
        """Returns not_found status when player not in DB or API."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            return_value=mock_response
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke(
                    {"player_names": ["NonexistentPlayer"]}
                )
            )

        player_result = result["NonexistentPlayer"]
        assert player_result["status"] == "not_found"

    def test_handles_api_error_gracefully(self, mock_repository):
        """API errors result in error status, not exceptions."""
        import requests

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.requests.get",
            side_effect=requests.RequestException("API Error")
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke(
                    {"player_names": ["UnknownPlayer"]}
                )
            )

        player_result = result["UnknownPlayer"]
        assert player_result["status"] == "error"


class TestMultipleMatches:
    """Test handling of ambiguous searches with multiple matches."""

    @pytest.fixture
    def db_with_similar_names(self):
        """Create database with players having similar names."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE nhl_player_stats (
                nhl_api_player_id INTEGER,
                full_name VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                game_date DATE
            )
        """)

        # Insert players with similar names
        similar_players = [
            (8471675, "Sidney Crosby", "Sidney", "Crosby"),
            (8471676, "Sidney Smith", "Sidney", "Smith"),
            (8471677, "Mike Crosby", "Mike", "Crosby"),
        ]

        for player_id, full_name, first_name, last_name in similar_players:
            conn.execute(
                "INSERT INTO nhl_player_stats VALUES (?, ?, ?, ?, ?)",
                [player_id, full_name, first_name, last_name, "2024-01-01"]
            )

        yield conn
        conn.close()

    def test_returns_multiple_matches_when_ambiguous(self, db_with_similar_names):
        """Ambiguous search returns multiple_matches status with all options."""
        mock_repo = Mock()
        mock_repo.conn = db_with_similar_names
        mock_repo.close = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.NHLPlayerStatsRepository",
            return_value=mock_repo
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Crosby"]})
            )

        player_result = result["Crosby"]
        assert player_result["status"] == "multiple_matches"
        assert "matches" in player_result
        assert len(player_result["matches"]) == 2  # Sidney Crosby and Mike Crosby

    def test_multiple_matches_include_player_details(self, db_with_similar_names):
        """Each match in multiple_matches includes player details."""
        mock_repo = Mock()
        mock_repo.conn = db_with_similar_names
        mock_repo.close = Mock()

        with patch(
            "tools.player_comparison.fuzzy_resolve_nhl_api_player_ids.NHLPlayerStatsRepository",
            return_value=mock_repo
        ):
            result = json.loads(
                fuzzy_resolve_nhl_api_player_ids.invoke({"player_names": ["Crosby"]})
            )

        matches = result["Crosby"]["matches"]
        for match in matches:
            assert "player_id" in match
            assert "full_name" in match
