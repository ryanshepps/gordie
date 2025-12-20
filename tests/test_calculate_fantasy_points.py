"""Tests for fantasy points calculation feature.

These tests verify that fantasy points are calculated correctly based on
player stats and the user's actual Yahoo Fantasy league scoring settings.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.player_comparison.calculate_fantasy_points import (
    calculate_fantasy_points,
    calculate_player_points,
    extract_scoring_settings,
)


def create_mock_settings(scoring: dict[str, float]):
    """Create a mock Yahoo Settings object with given scoring values."""
    mock_settings = MagicMock()
    mock_stats = []
    for abbr, value in scoring.items():
        stat = MagicMock()
        stat.abbr = abbr
        stat.value = value
        mock_stats.append(stat)
    mock_settings.stat_modifiers.stats = mock_stats
    return mock_settings


class TestExtractScoringSettings:
    """Test extraction of scoring settings from Yahoo API response."""

    def test_extracts_scoring_from_stat_modifiers(self):
        """Should extract point values from stat_modifiers."""
        settings = create_mock_settings({"G": 3.0, "A": 2.0, "SOG": 0.5})

        scoring = extract_scoring_settings(settings)

        assert scoring["G"] == 3.0
        assert scoring["A"] == 2.0
        assert scoring["SOG"] == 0.5

    def test_raises_when_stat_modifiers_missing(self):
        """Should raise ValueError when stat_modifiers is None."""
        settings = MagicMock()
        settings.stat_modifiers = None

        with pytest.raises(ValueError, match="missing stat_modifiers"):
            extract_scoring_settings(settings)

    def test_raises_when_stats_empty(self):
        """Should raise ValueError when stats list is empty."""
        settings = MagicMock()
        settings.stat_modifiers.stats = []

        with pytest.raises(ValueError, match="no stats defined"):
            extract_scoring_settings(settings)


class TestCalculatePlayerPoints:
    """Test point calculation for individual players."""

    def test_calculates_points_using_league_scoring(self):
        """Should use the provided scoring settings, not defaults."""
        player_stats = {"goals": 5, "assists": 10, "games_played": 10}
        # Custom scoring: 5 points per goal, 3 per assist
        scoring = {"G": 5.0, "A": 3.0}

        result = calculate_player_points(player_stats, scoring)

        # 5 goals * 5 pts + 10 assists * 3 pts = 25 + 30 = 55
        assert result["total_fantasy_points"] == 55.0
        assert result["breakdown"]["goals"] == 25.0
        assert result["breakdown"]["assists"] == 30.0

    def test_only_counts_stats_in_league_scoring(self):
        """Should only count stats that are in the league's scoring settings."""
        player_stats = {
            "goals": 5,
            "assists": 10,
            "hits": 20,  # Not in scoring
            "games_played": 10,
        }
        scoring = {"G": 3.0, "A": 2.0}  # No hits

        result = calculate_player_points(player_stats, scoring)

        assert result["total_fantasy_points"] == 35.0  # 5*3 + 10*2
        assert "hits" not in result["breakdown"]

    def test_handles_negative_plus_minus(self):
        """Negative plus/minus should subtract points."""
        player_stats = {"plus_minus": -10, "games_played": 10}
        scoring = {"+/-": 1.0}

        result = calculate_player_points(player_stats, scoring)

        assert result["total_fantasy_points"] == -10.0
        assert result["breakdown"]["plus_minus"] == -10.0

    def test_calculates_points_per_game(self):
        """Should calculate fantasy points per game."""
        player_stats = {"goals": 10, "games_played": 5}
        scoring = {"G": 2.0}

        result = calculate_player_points(player_stats, scoring)

        assert result["fantasy_points_per_game"] == 4.0  # 20 / 5

    def test_handles_zero_games_played(self):
        """Should return 0 ppg when games_played is 0."""
        player_stats = {"goals": 0, "games_played": 0}
        scoring = {"G": 3.0}

        result = calculate_player_points(player_stats, scoring)

        assert result["fantasy_points_per_game"] == 0


class TestCalculateFantasyPointsTool:
    """Test the full tool integration."""

    def test_uses_league_scoring_settings(self):
        """Should fetch and use actual league scoring settings."""
        stats = {"player_a": {"goals": 5, "assists": 8, "games_played": 10}}
        mock_settings = create_mock_settings({"G": 4.0, "A": 3.0})

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            mock_client.return_value.query.get_league_settings.return_value = (
                mock_settings
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": json.dumps(stats),
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        # 5 goals * 4 pts + 8 assists * 3 pts = 20 + 24 = 44
        assert result["player_a"]["total_fantasy_points"] == 44.0

    def test_errors_when_league_settings_unavailable(self):
        """Should return error when league settings cannot be fetched."""
        stats = {"player_a": {"goals": 5, "games_played": 10}}

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            # Return settings with no stat_modifiers
            mock_settings = MagicMock()
            mock_settings.stat_modifiers = None
            mock_client.return_value.query.get_league_settings.return_value = (
                mock_settings
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": json.dumps(stats),
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        assert result["status"] == "error"
        assert "scoring settings" in result["error"].lower()

    def test_errors_when_yahoo_api_fails(self):
        """Should return error when Yahoo API call fails."""
        stats = {"player_a": {"goals": 5, "games_played": 10}}

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            mock_client.return_value.query.get_league_settings.side_effect = Exception(
                "API timeout"
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": json.dumps(stats),
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        assert result["status"] == "error"

    def test_calculates_for_multiple_players(self):
        """Should calculate points for all players in input."""
        stats = {
            "player_a": {"goals": 5, "assists": 5, "games_played": 10},
            "player_b": {"goals": 3, "assists": 8, "games_played": 10},
        }
        mock_settings = create_mock_settings({"G": 3.0, "A": 2.0})

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            mock_client.return_value.query.get_league_settings.return_value = (
                mock_settings
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": json.dumps(stats),
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        assert result["player_a"]["total_fantasy_points"] == 25.0  # 5*3 + 5*2
        assert result["player_b"]["total_fantasy_points"] == 25.0  # 3*3 + 8*2

    def test_preserves_error_status_for_failed_players(self):
        """Players with error status should be passed through unchanged."""
        stats = {
            "player_a": {"goals": 5, "games_played": 10},
            "player_b": {"status": "error", "error": "Player not found"},
        }
        mock_settings = create_mock_settings({"G": 3.0})

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            mock_client.return_value.query.get_league_settings.return_value = (
                mock_settings
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": json.dumps(stats),
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        assert "total_fantasy_points" in result["player_a"]
        assert result["player_b"]["status"] == "error"

    def test_returns_error_for_invalid_json(self):
        """Should return error for malformed JSON input."""
        mock_settings = create_mock_settings({"G": 3.0})

        with patch(
            "tools.player_comparison.calculate_fantasy_points.AuthenticatedYahooClient"
        ) as mock_client:
            mock_client.return_value.query.get_league_settings.return_value = (
                mock_settings
            )

            result = json.loads(
                calculate_fantasy_points.invoke(
                    {
                        "player_stats": "not valid json {",
                        "league_id": "12345",
                        "user_email": "test@example.com",
                    }
                )
            )

        assert result["status"] == "error"
        assert "json" in result["error"].lower()
