"""Tests for player comparison feature.

These tests verify the behavior of comparing NHL players for fantasy hockey
decisions. Tests focus on outcomes users care about:
- Which player is recommended
- Confidence level of recommendations
- Handling of edge cases (ties, missing data, errors)
"""

import json

from tools.hockey.player.compare_players_comprehensive import (
    compare_players_comprehensive,
)


class TestPlayerRecommendation:
    """Test that the comparison tool recommends the better player."""

    def test_recommends_higher_scoring_player(
        self, sample_player_stats_json, sample_fantasy_points_json
    ):
        """Player with more fantasy points should be recommended."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": sample_fantasy_points_json,
                }
            )
        )

        # McDavid (8478402) has 68.4 fantasy points vs Draisaitl's 52.0
        assert result["recommendation"] == "8478402"

    def test_high_confidence_for_clear_winner(
        self, sample_player_stats_json, sample_fantasy_points_json
    ):
        """Large score difference should yield high confidence."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": sample_fantasy_points_json,
                }
            )
        )

        assert result["confidence"] == "High"

    def test_medium_confidence_for_close_matchup(self):
        """Nearly identical players should yield medium confidence."""
        # Two nearly identical players - same stats across the board
        similar_stats = {
            "player_a": {
                "games_played": 10,
                "goals": 5,
                "assists": 8,
                "points": 13,
                "plus_minus": 3,
                "sog": 30,
                "hits": 10,
                "blocked_shots": 5,
                "points_per_game": 1.3,
                "goals_per_game": 0.5,
                "sog_per_game": 3.0,
            },
            "player_b": {
                "games_played": 10,
                "goals": 5,
                "assists": 8,
                "points": 13,
                "plus_minus": 3,
                "sog": 30,
                "hits": 10,
                "blocked_shots": 5,
                "points_per_game": 1.3,
                "goals_per_game": 0.5,
                "sog_per_game": 3.0,
            },
        }
        # Identical fantasy points
        similar_fantasy = {
            "player_a": {"total_fantasy_points": 35.0, "games_played": 10},
            "player_b": {"total_fantasy_points": 35.0, "games_played": 10},
        }

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": json.dumps(similar_stats),
                    "fantasy_points": json.dumps(similar_fantasy),
                }
            )
        )

        assert result["confidence"] == "Medium"


class TestComparisonOutput:
    """Test that comparison provides useful information to users."""

    def test_includes_overall_scores_for_all_players(
        self, sample_player_stats_json, sample_fantasy_points_json
    ):
        """Each player should have an overall score."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": sample_fantasy_points_json,
                }
            )
        )

        assert "8478402" in result["overall_scores"]
        assert "8477934" in result["overall_scores"]
        assert isinstance(result["overall_scores"]["8478402"], (int, float))
        assert isinstance(result["overall_scores"]["8477934"], (int, float))

    def test_includes_stats_comparison(self, sample_player_stats_json, sample_fantasy_points_json):
        """Stats comparison should include key fantasy-relevant stats."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": sample_fantasy_points_json,
                }
            )
        )

        for player_id in ["8478402", "8477934"]:
            stats = result["stats_comparison"][player_id]
            assert "goals" in stats
            assert "assists" in stats
            assert "points" in stats
            assert "fantasy_points" in stats

    def test_includes_category_breakdown(
        self, sample_player_stats_json, sample_fantasy_points_json
    ):
        """Should show how players score in each evaluation category."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": sample_fantasy_points_json,
                }
            )
        )

        for player_id in ["8478402", "8477934"]:
            breakdown = result["category_breakdown"][player_id]
            assert "fantasy_points" in breakdown
            assert "general_performance" in breakdown
            assert "position_specific" in breakdown


class TestPositionHandling:
    """Test that comparison handles different positions appropriately."""

    def test_compares_forwards_using_forward_metrics(self, sample_player_stats_json):
        """Forward comparison should emphasize goals and offensive stats."""
        fantasy_points = {
            "8478402": {"total_fantasy_points": 68.4},
            "8477934": {"total_fantasy_points": 52.0},
        }
        positions = {"8478402": "C", "8477934": "C"}

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": sample_player_stats_json,
                    "fantasy_points": json.dumps(fantasy_points),
                    "player_positions": json.dumps(positions),
                }
            )
        )

        # Should still produce a valid recommendation
        assert result["recommendation"] in ["8478402", "8477934"]
        assert "overall_scores" in result

    def test_compares_defensemen_using_defensive_metrics(self, defensive_player_stats):
        """Defense comparison should consider blocks, hits, and assists."""
        # Add a second defenseman for comparison
        stats = defensive_player_stats.copy()
        stats["8479323"] = {  # Another defenseman
            "player_id": 8479323,
            "games_played": 10,
            "goals": 1,
            "assists": 8,
            "points": 9,
            "plus_minus": 4,
            "hits": 25,
            "blocked_shots": 22,
            "sog": 20,
            "points_per_game": 0.9,
            "goals_per_game": 0.1,
            "assists_per_game": 0.8,
            "sog_per_game": 2.0,
        }

        fantasy_points = {
            "8480069": {"total_fantasy_points": 40.0},
            "8479323": {"total_fantasy_points": 35.0},
        }
        positions = {"8480069": "D", "8479323": "D"}

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": json.dumps(stats),
                    "fantasy_points": json.dumps(fantasy_points),
                    "player_positions": json.dumps(positions),
                }
            )
        )

        assert result["recommendation"] in ["8480069", "8479323"]


class TestErrorHandling:
    """Test graceful handling of edge cases and errors."""

    def test_requires_at_least_two_players(self):
        """Should error when given fewer than 2 players."""
        single_player_stats = {
            "8478402": {
                "games_played": 10,
                "goals": 8,
                "points_per_game": 2.3,
            }
        }
        single_fantasy = {"8478402": {"total_fantasy_points": 68.4}}

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": json.dumps(single_player_stats),
                    "fantasy_points": json.dumps(single_fantasy),
                }
            )
        )

        assert result["status"] == "error"
        assert "2" in result["message"].lower() or "two" in result["message"].lower()

    def test_handles_missing_stats_gracefully(self):
        """Should handle players with minimal stats."""
        minimal_stats = {
            "player_a": {"games_played": 5, "goals": 2, "assists": 3},
            "player_b": {"games_played": 5, "goals": 1, "assists": 4},
        }
        fantasy_points = {
            "player_a": {"total_fantasy_points": 15.0},
            "player_b": {"total_fantasy_points": 14.0},
        }

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": json.dumps(minimal_stats),
                    "fantasy_points": json.dumps(fantasy_points),
                }
            )
        )

        # Should still produce a recommendation
        assert "recommendation" in result
        assert result["recommendation"] in ["player_a", "player_b"]

    def test_handles_invalid_json_input(self):
        """Should return error for malformed JSON."""
        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": "not valid json",
                    "fantasy_points": "{}",
                }
            )
        )

        assert result["status"] == "error"

    def test_skips_players_with_error_status(self):
        """Players marked as error should be excluded from comparison."""
        stats = {
            "player_a": {"status": "error", "error": "Player not found"},
            "player_b": {
                "games_played": 10,
                "goals": 5,
                "points_per_game": 1.0,
                "goals_per_game": 0.5,
                "sog_per_game": 3.0,
            },
            "player_c": {
                "games_played": 10,
                "goals": 3,
                "points_per_game": 0.8,
                "goals_per_game": 0.3,
                "sog_per_game": 2.5,
            },
        }
        fantasy_points = {
            "player_a": {"status": "error"},
            "player_b": {"total_fantasy_points": 30.0},
            "player_c": {"total_fantasy_points": 25.0},
        }

        result = json.loads(
            compare_players_comprehensive.invoke(
                {
                    "player_stats": json.dumps(stats),
                    "fantasy_points": json.dumps(fantasy_points),
                }
            )
        )

        # Should compare only valid players
        assert result["recommendation"] in ["player_b", "player_c"]
        assert "player_a" not in result.get("overall_scores", {})
