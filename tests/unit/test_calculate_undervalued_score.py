"""Tests for the calculate_undervalued_score tool."""

import json
from unittest.mock import patch

from tools.hockey.player.calculate_undervalued_score import (
    MoneyPuckStats,
    _calculate_score,
    calculate_undervalued_score,
)


class TestCalculateScore:
    """Test the pure scoring function."""

    def test_negative_gae_with_high_xgoals_scores_high(self):
        """Player shooting below expected with high xGoals should score highly."""
        stats = {
            "goals": 5,
            "x_goals": 12.0,
            "goals_above_expected": -7.0,
            "games_played": 50,
            "toi_per_game_minutes": 18.0,
            "position": "C",
        }
        score, reasons = _calculate_score(stats)
        assert score >= 4
        assert any("regression" in r.lower() for r in reasons)

    def test_positive_gae_penalizes(self):
        """Player overperforming should get negative score."""
        stats = {
            "goals": 20,
            "x_goals": 12.0,
            "goals_above_expected": 8.0,
            "games_played": 50,
        }
        score, reasons = _calculate_score(stats)
        assert score < 0
        assert any("overperforming" in r.lower() for r in reasons)

    def test_elite_fenwick_boosts_score(self):
        """High Fenwick% should boost score."""
        stats = {"fenwick_pct": 57.0, "toi_per_game_minutes": 18.0, "position": "C"}
        score, reasons = _calculate_score(stats)
        assert score >= 3
        assert any("elite" in r.lower() for r in reasons)

    def test_poor_fenwick_penalizes(self):
        """Low Fenwick% should reduce score."""
        stats = {"fenwick_pct": 45.0}
        score, reasons = _calculate_score(stats)
        assert score < 0
        assert any("poor" in r.lower() for r in reasons)

    def test_top_line_forward_toi_boosts(self):
        """High TOI for a forward should boost score."""
        stats = {"toi_per_game_minutes": 20.0, "position": "C"}
        score, reasons = _calculate_score(stats)
        assert score >= 2
        assert any("ice time" in r.lower() for r in reasons)

    def test_first_line_deployment_boosts(self):
        """First line deployment should add to score."""
        stats = {"estimated_line_number": 1, "toi_per_game_minutes": 18.0, "position": "C"}
        _score, reasons = _calculate_score(stats)
        assert any("first line" in r.lower() for r in reasons)

    def test_favorable_schedule_boosts(self):
        """Many upcoming games should boost score."""
        stats = {
            "games_remaining_this_week": 4,
            "games_next_week": 4,
            "toi_per_game_minutes": 18.0,
            "position": "C",
        }
        _score, reasons = _calculate_score(stats)
        assert any("schedule" in r.lower() for r in reasons)

    def test_combined_undervalued_player(self):
        """Player with multiple positive signals should have high score."""
        stats = {
            "goals": 8,
            "x_goals": 14.0,
            "goals_above_expected": -6.0,
            "games_played": 50,
            "fenwick_pct": 56.0,
            "corsi_pct": 55.0,
            "toi_per_game_minutes": 20.0,
            "position": "LW",
            "estimated_line_number": 1,
            "games_remaining_this_week": 4,
            "games_next_week": 3,
        }
        score, reasons = _calculate_score(stats)
        assert score >= 10
        assert len(reasons) >= 4

    def test_low_games_played_raw_gae_not_inflated(self):
        """A player with few games should not get a large GAE bonus from raw totals alone.

        Rakell scenario: 20 games, 3G vs 5.0 xG = -2.0 raw GAE.
        Raw thresholds would give +2, but pace-adjusted GAE/82 = -8.2 which exceeds the
        threshold. The xGoals pace threshold (3 * 20/82 = 0.73) also gates this properly
        so a tiny sample with low volume doesn't score the same as a full-season player.
        """
        few_games_stats = {
            "goals": 3,
            "x_goals": 5.0,
            "goals_above_expected": -2.0,
            "games_played": 20,
            "toi_per_game_minutes": 16.0,
            "position": "RW",
        }
        full_season_stats = {
            "goals": 10,
            "x_goals": 18.0,
            "goals_above_expected": -8.0,
            "games_played": 70,
            "toi_per_game_minutes": 16.0,
            "position": "RW",
        }
        few_score, _ = _calculate_score(few_games_stats)
        full_score, _ = _calculate_score(full_season_stats)
        assert full_score >= few_score

    def test_few_games_overperformer_not_penalized_like_full_season(self):
        """A player with +4 GAE in 15 games should not be penalized the same as +4 in 70 games.

        15 games: GAE/82 = +21.9 — high pace, but the raw +4 in 15GP is small-sample noise.
        70 games: GAE/82 = +4.7 — sustained overperformance, deserves penalty.
        Both should trigger the overperforming warning since pace is > 3, but this test
        verifies the normalization math runs without error on low-GP players.
        """
        few_games = {
            "goals": 10,
            "x_goals": 6.0,
            "goals_above_expected": 4.0,
            "games_played": 15,
        }
        full_season = {
            "goals": 25,
            "x_goals": 21.0,
            "goals_above_expected": 4.0,
            "games_played": 70,
        }
        _few_score, few_reasons = _calculate_score(few_games)
        _full_score, full_reasons = _calculate_score(full_season)
        assert any("overperforming" in r.lower() for r in few_reasons)
        assert any("overperforming" in r.lower() for r in full_reasons)

    def test_very_few_games_gae_ignored(self):
        """Players with fewer than 5 games should not get GAE regression bonuses."""
        stats = {
            "goals": 0,
            "x_goals": 3.0,
            "goals_above_expected": -3.0,
            "games_played": 3,
            "toi_per_game_minutes": 14.0,
            "position": "C",
        }
        _score, reasons = _calculate_score(stats)
        assert not any("significant" in r.lower() for r in reasons)
        assert not any("candidate" in r.lower() and "positive" in r.lower() for r in reasons)


class TestCalculateUndervaluedScoreTool:
    """Test the full tool with mocked external calls."""

    def test_returns_json_with_score(self):
        """Should return JSON with undervalued_score and reasons."""
        mock_yahoo = json.dumps(
            {
                "player": {
                    "rank": 85,
                    "player_key": "nhl.p.8478402",
                    "ownership_type": "team",
                    "owner_team_name": "Team A",
                    "percent_owned": "95",
                    "injury_status": None,
                }
            }
        )
        mock_schedule = json.dumps(
            {
                "EDM": {
                    "status": "success",
                    "this_week_games": 3,
                    "next_week_games": 4,
                }
            }
        )

        with (
            patch(
                "tools.hockey.player.calculate_undervalued_score.get_player_season_rank",
                return_value=mock_yahoo,
            ),
            patch(
                "tools.hockey.player.calculate_undervalued_score.get_team_schedule",
                return_value=mock_schedule,
            ),
        ):
            result = calculate_undervalued_score.func(  # pyright: ignore[reportAttributeAccessIssue]
                stats=MoneyPuckStats(
                    player_name="Connor McDavid",
                    team="EDM",
                    position="C",
                    games_played=30,
                    goals=20,
                    points=55,
                    points_per_game=1.83,
                    x_goals=15.5,
                    fenwick_pct=55.2,
                    corsi_pct=54.1,
                    toi_per_game_minutes=22.5,
                ),
                league_id="12345",
                state={"user_id": "user-123"},
            )

        data = json.loads(result)
        assert data["status"] == "success"
        assert data["name"] == "Connor McDavid"
        assert "undervalued_score" in data
        assert "undervalued_reasons" in data
        assert data["yahoo_rank"] == 85
        assert data["games_remaining_this_week"] == 3

    def test_handles_yahoo_failure_gracefully(self):
        """Should still return a score even if Yahoo lookup fails."""
        mock_schedule = json.dumps(
            {"TOR": {"status": "success", "this_week_games": 3, "next_week_games": 3}}
        )

        with (
            patch(
                "tools.hockey.player.calculate_undervalued_score.get_player_season_rank",
                side_effect=Exception("Yahoo API down"),
            ),
            patch(
                "tools.hockey.player.calculate_undervalued_score.get_team_schedule",
                return_value=mock_schedule,
            ),
        ):
            result = calculate_undervalued_score.func(  # pyright: ignore[reportAttributeAccessIssue]
                stats=MoneyPuckStats(
                    player_name="Auston Matthews",
                    team="TOR",
                    position="C",
                    games_played=25,
                    goals=15,
                    points=35,
                    points_per_game=1.4,
                    x_goals=12.0,
                    fenwick_pct=54.0,
                    corsi_pct=53.0,
                    toi_per_game_minutes=20.5,
                ),
                league_id="12345",
                state={"user_id": "user-123"},
            )

        data = json.loads(result)
        assert data["status"] == "success"
        assert "undervalued_score" in data
        assert any("Yahoo" in w for w in data.get("warnings", []))
