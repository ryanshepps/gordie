"""Unit tests for the calculate_undervalued_score function."""

from tools.player_comparison.get_comprehensive_player_stats import (
    calculate_undervalued_score,
)


class TestUndervaluedScoreCalculation:
    """
    Unit tests for the calculate_undervalued_score function.

    Verifies that players with strong underlying stats but poor production
    are correctly identified as undervalued (positive regression candidates).
    """

    def test_negative_gae_increases_score(self):
        """Player with goals below expected should have higher undervalued score."""
        # Player shooting below expected - due for positive regression
        unlucky_player = {
            "goals": 5,
            "x_goals": 10.0,
            "goals_above_expected": -5.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        # Player shooting at expected
        average_player = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        unlucky_score, unlucky_reasons = calculate_undervalued_score(unlucky_player)
        average_score, _average_reasons = calculate_undervalued_score(average_player)

        assert unlucky_score > average_score, (
            f"Unlucky player (GAE: -5) should score higher than average player. "
            f"Got unlucky={unlucky_score}, average={average_score}"
        )
        assert any("regression" in r.lower() for r in unlucky_reasons), (
            f"Should mention regression in reasons: {unlucky_reasons}"
        )

    def test_positive_gae_decreases_score(self):
        """Player overperforming xGoals should have lower/negative score."""
        # Player shooting way above expected - likely to regress DOWN
        overperformer = {
            "goals": 15,
            "x_goals": 8.0,
            "goals_above_expected": 7.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        score, reasons = calculate_undervalued_score(overperformer)

        assert score < 0, f"Overperformer (GAE: +7) should have negative score. Got {score}"
        assert any("warning" in r.lower() or "overperforming" in r.lower() for r in reasons), (
            f"Should warn about regression down: {reasons}"
        )

    def test_strong_fenwick_increases_score(self):
        """Player with elite possession (Fenwick > 55%) should score higher."""
        elite_possession = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 57.0,
            "corsi_pct": 56.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        average_possession = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        elite_score, elite_reasons = calculate_undervalued_score(elite_possession)
        avg_score, _ = calculate_undervalued_score(average_possession)

        assert elite_score > avg_score, (
            f"Elite possession player should score higher. "
            f"Got elite={elite_score}, average={avg_score}"
        )
        assert any("possession" in r.lower() or "fenwick" in r.lower() for r in elite_reasons)

    def test_poor_fenwick_decreases_score(self):
        """Player with poor possession (Fenwick < 47%) should score lower."""
        poor_possession = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 44.0,
            "corsi_pct": 43.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
        }

        score, reasons = calculate_undervalued_score(poor_possession)

        assert score < 0, f"Poor possession player should have negative score. Got {score}"
        assert any("warning" in r.lower() or "poor" in r.lower() for r in reasons)

    def test_high_toi_forward_increases_score(self):
        """Forward with top-line ice time (>19 min) should score higher."""
        top_line_forward = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 20.5,
            "position": "LW",
        }

        bottom_six_forward = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 12.0,
            "position": "LW",
        }

        top_score, top_reasons = calculate_undervalued_score(top_line_forward)
        bottom_score, _ = calculate_undervalued_score(bottom_six_forward)

        assert top_score > bottom_score, (
            f"Top-line forward should score higher. Got top={top_score}, bottom={bottom_score}"
        )
        assert any("ice time" in r.lower() or "top-line" in r.lower() for r in top_reasons)

    def test_high_toi_defenseman_increases_score(self):
        """Defenseman with top-pairing ice time (>22 min) should score higher."""
        top_pair_d = {
            "goals": 5,
            "x_goals": 5.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 24.0,
            "position": "D",
        }

        third_pair_d = {
            "goals": 5,
            "x_goals": 5.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 14.0,
            "position": "D",
        }

        top_score, top_reasons = calculate_undervalued_score(top_pair_d)
        third_score, _ = calculate_undervalued_score(third_pair_d)

        assert top_score > third_score, (
            f"Top-pair D should score higher. Got top={top_score}, third={third_score}"
        )
        assert any("pairing" in r.lower() or "ice time" in r.lower() for r in top_reasons)

    def test_first_line_deployment_increases_score(self):
        """Player on first line should score higher than fourth line."""
        first_liner = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "estimated_line_number": 1,
        }

        fourth_liner = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "estimated_line_number": 4,
        }

        first_score, first_reasons = calculate_undervalued_score(first_liner)
        fourth_score, fourth_reasons = calculate_undervalued_score(fourth_liner)

        assert first_score > fourth_score, (
            f"First liner should score higher. Got first={first_score}, fourth={fourth_score}"
        )
        assert any("first line" in r.lower() for r in first_reasons)
        assert any("fourth line" in r.lower() for r in fourth_reasons)

    def test_underranked_player_increases_score(self):
        """Player ranked worse than PPG suggests should score higher."""
        underranked = {
            "goals": 15,
            "x_goals": 15.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "yahoo_rank": 180,  # Ranked poorly
            "points_per_game": 0.9,  # But elite PPG
            "games_played": 30,
        }

        fairly_ranked = {
            "goals": 15,
            "x_goals": 15.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "yahoo_rank": 40,  # Ranked appropriately for 0.9 PPG
            "points_per_game": 0.9,
            "games_played": 30,
        }

        underranked_score, underranked_reasons = calculate_undervalued_score(underranked)
        fair_score, _ = calculate_undervalued_score(fairly_ranked)

        assert underranked_score > fair_score, (
            f"Underranked player should score higher. "
            f"Got underranked={underranked_score}, fair={fair_score}"
        )
        assert any("underranked" in r.lower() for r in underranked_reasons)

    def test_favorable_schedule_increases_score(self):
        """Player with favorable upcoming schedule should score slightly higher."""
        busy_schedule = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "games_remaining_this_week": 4,
            "games_next_week": 4,
        }

        light_schedule = {
            "goals": 10,
            "x_goals": 10.0,
            "goals_above_expected": 0.0,
            "fenwick_pct": 50.0,
            "corsi_pct": 50.0,
            "toi_per_game_minutes": 15.0,
            "position": "C",
            "games_remaining_this_week": 1,
            "games_next_week": 2,
        }

        busy_score, busy_reasons = calculate_undervalued_score(busy_schedule)
        light_score, _light_reasons = calculate_undervalued_score(light_schedule)

        assert busy_score > light_score, (
            f"Busy schedule player should score higher. Got busy={busy_score}, light={light_score}"
        )
        assert any("schedule" in r.lower() for r in busy_reasons)

    def test_combined_undervalued_player(self):
        """Ideal undervalued player: negative GAE, strong possession, good TOI, top line."""
        ideal_target = {
            "goals": 8,
            "x_goals": 14.0,
            "goals_above_expected": -6.0,  # Significant negative GAE
            "fenwick_pct": 56.0,  # Elite possession
            "corsi_pct": 55.0,
            "toi_per_game_minutes": 19.5,  # Top-line TOI
            "position": "LW",
            "estimated_line_number": 1,  # First line
            "yahoo_rank": 120,  # Underranked
            "points_per_game": 0.7,  # Should be ~rank 80
            "games_played": 25,
            "games_remaining_this_week": 4,
            "games_next_week": 3,
        }

        score, reasons = calculate_undervalued_score(ideal_target)

        # Should have very high score (likely 8+)
        assert score >= 7.0, (
            f"Ideal undervalued player should have score >= 7. Got {score}. Reasons: {reasons}"
        )
        # Should have multiple positive reasons
        assert len([r for r in reasons if "warning" not in r.lower()]) >= 4, (
            f"Should have at least 4 positive reasons. Got: {reasons}"
        )

    def test_overvalued_player(self):
        """Player to avoid: positive GAE, poor possession, low TOI."""
        sell_candidate = {
            "goals": 12,
            "x_goals": 6.0,
            "goals_above_expected": 6.0,  # Significantly overperforming
            "fenwick_pct": 45.0,  # Poor possession
            "corsi_pct": 44.0,
            "toi_per_game_minutes": 11.0,  # Low TOI
            "position": "C",
            "estimated_line_number": 4,  # Fourth line
        }

        score, reasons = calculate_undervalued_score(sell_candidate)

        # Should have negative score
        assert score < 0, (
            f"Overvalued player should have negative score. Got {score}. Reasons: {reasons}"
        )
        # Should have warnings
        assert len([r for r in reasons if "warning" in r.lower()]) >= 1, (
            f"Should have at least 1 warning. Got: {reasons}"
        )
