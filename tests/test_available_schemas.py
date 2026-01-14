"""Unit tests for available players subagent Pydantic schemas."""

import pytest
from pydantic import ValidationError

from agent.subagents.available import (
    AvailablePickup,
    AvailablePlayersResponse,
    DropCandidate,
    PlayerStats,
)


class TestPlayerStatsValidation:
    """Test PlayerStats schema validators."""

    def test_toi_must_be_realistic(self):
        """TOI validator should reject unrealistic values."""
        # TOI too low
        with pytest.raises(ValidationError, match=r"TOI of .* is unrealistic"):
            PlayerStats(
                name="Test Player",
                team="TOR",
                position="C",
                games_played=50,
                goals=20,
                assists=30,
                points=50,
                toi_per_game=3.0,  # Too low
                x_goals=15.0,
                goals_above_expected=5.0,
                fenwick_pct=50.0,
                corsi_pct=50.0,
                points_per_game=1.0,
            )

        # TOI too high
        with pytest.raises(ValidationError, match=r"TOI of .* is unrealistic"):
            PlayerStats(
                name="Test Player",
                team="TOR",
                position="C",
                games_played=50,
                goals=20,
                assists=30,
                points=50,
                toi_per_game=35.0,  # Too high
                x_goals=15.0,
                goals_above_expected=5.0,
                fenwick_pct=50.0,
                corsi_pct=50.0,
                points_per_game=1.0,
            )

    def test_fenwick_corsi_must_be_realistic(self):
        """Fenwick/Corsi validators should reject unrealistic values."""
        # Fenwick too low
        with pytest.raises(ValidationError, match=r"Percentage of .* is unrealistic"):
            PlayerStats(
                name="Test Player",
                team="TOR",
                position="C",
                games_played=50,
                goals=20,
                assists=30,
                points=50,
                toi_per_game=18.0,
                x_goals=15.0,
                goals_above_expected=5.0,
                fenwick_pct=25.0,  # Too low
                corsi_pct=50.0,
                points_per_game=1.0,
            )

        # Corsi too high
        with pytest.raises(ValidationError, match=r"Percentage of .* is unrealistic"):
            PlayerStats(
                name="Test Player",
                team="TOR",
                position="C",
                games_played=50,
                goals=20,
                assists=30,
                points=50,
                toi_per_game=18.0,
                x_goals=15.0,
                goals_above_expected=5.0,
                fenwick_pct=50.0,
                corsi_pct=75.0,  # Too high
                points_per_game=1.0,
            )

    def test_valid_player_stats(self):
        """Valid PlayerStats should pass validation."""
        player = PlayerStats(
            name="Test Player",
            team="TOR",
            position="C",
            yahoo_rank=50,
            games_played=50,
            goals=20,
            assists=30,
            points=50,
            toi_per_game=18.5,
            x_goals=15.0,
            goals_above_expected=5.0,
            fenwick_pct=52.0,
            corsi_pct=51.5,
            points_per_game=1.0,
            games_remaining_this_week=2,
            games_next_week=3,
            undervalued_score=4.5,
        )
        assert player.name == "Test Player"
        assert player.toi_per_game == 18.5
        assert player.fenwick_pct == 52.0


class TestAvailablePickupValidation:
    """Test AvailablePickup schema validators."""

    def test_pitch_must_contain_stats(self):
        """Pitch validator should require specific stats."""
        # Pitch without stats (long enough to pass min_length but missing stat keywords)
        with pytest.raises(ValidationError, match="Pitch must include specific stats"):
            AvailablePickup(
                player_name="Test Player",
                availability_type="FA",
                stats_summary="This player is good and has been performing well recently with consistent production.",
                pitch="This player is ranked well and is a good pickup for your team because he is available and performing consistently. He has been producing at a high level and is a quality addition to any roster. You should definitely consider adding him.",
                reasoning="He's better than other options and you should pick him up. His overall performance has been solid and he will help your team. Consider adding this player to improve your roster depth and scoring.",
                priority_level="strong_add",
            )

    def test_pitch_with_stats_passes(self):
        """Pitch with specific stats should pass validation."""
        pickup = AvailablePickup(
            player_name="Test Player",
            availability_type="FA",
            stats_summary="20 goals, 30 assists in 50 games. 15.0 xGoals, 52% Fenwick. 5 games next week.",
            pitch="Test Player has 15.0 xGoals with only 20 actual goals (-5.0 goals above expected), showing strong regression potential. Fenwick% of 52.0 indicates solid possession. Playing 18.5 min/game on line 1. Schedule: 5 games next 2 weeks.",
            reasoning="Better xGoals (15.0 vs 12.0), Fenwick% (52% vs 48%), and schedule (5 games vs 3). Top line deployment with quality linemates.",
            priority_level="strong_add",
        )
        assert pickup.player_name == "Test Player"

    def test_reasoning_must_be_analytical(self):
        """Reasoning validator should require stats analysis."""
        # Reasoning without stats (long enough but missing stat keywords)
        with pytest.raises(ValidationError, match="Reasoning must include advanced stats"):
            AvailablePickup(
                player_name="Test Player",
                availability_type="FA",
                stats_summary="20 goals, 30 assists. Good player with potential for continued success.",
                pitch="This player has 15.0 xGoals and 52% Fenwick with a favorable schedule of 5 games next week. He's been producing well and should continue to perform at a high level. The deployment and opportunities are favorable for continued success.",
                reasoning="This player is just better overall and should be picked up instead of your current player. He will improve your team and provide better production. The overall quality is higher with this player on your roster.",
                priority_level="strong_add",
            )


class TestDropCandidateValidation:
    """Test DropCandidate schema validators."""

    def test_valid_drop_candidate(self):
        """Valid DropCandidate should pass validation."""
        drop = DropCandidate(
            player_name="Drop Player",
            stats_summary="8 goals, 12 assists in 45 games. 3.2 goals above expected, 46.8% Fenwick.",
            drop_rationale="Shooting 15% above expected (3.2 GAE). Fenwick% of 46.8 shows poor possession. Only 3 games next 2 weeks. 4th line deployment limits upside.",
        )
        assert drop.player_name == "Drop Player"
        assert len(drop.drop_rationale) >= 80


class TestAvailablePlayersResponseValidation:
    """Test AvailablePlayersResponse schema validators."""

    def test_validate_completeness_rejects_missing_stats(self):
        """Model validator should reject responses missing player stats."""
        # Missing stats for drop candidate
        with pytest.raises(ValidationError, match="Missing stats for drop candidate"):
            AvailablePlayersResponse(
                drop_candidates=[
                    DropCandidate(
                        player_name="Missing Stats Player",
                        stats_summary="Some stats here to meet minimum length requirement.",
                        drop_rationale="This player should be dropped because of various reasons that are detailed here.",
                    )
                ],
                player_stats=[
                    PlayerStats(
                        name="Other Player",
                        team="TOR",
                        position="C",
                        games_played=50,
                        goals=20,
                        assists=30,
                        points=50,
                        toi_per_game=18.0,
                        x_goals=15.0,
                        goals_above_expected=5.0,
                        fenwick_pct=50.0,
                        corsi_pct=50.0,
                        points_per_game=1.0,
                    )
                ],
                free_agent_recommendations=[],
                waiver_recommendations=[],
                summary="Summary with xGoals and Fenwick% analysis. Free agents can be added immediately while waivers require a claim.",
            )

    def test_validate_completeness_rejects_missing_fa_stats(self):
        """Model validator should reject responses missing FA pickup stats."""
        with pytest.raises(ValidationError, match="Missing stats for FA pickup"):
            AvailablePlayersResponse(
                drop_candidates=[],
                player_stats=[
                    PlayerStats(
                        name="Drop Player",
                        team="TOR",
                        position="C",
                        games_played=50,
                        goals=20,
                        assists=30,
                        points=50,
                        toi_per_game=18.0,
                        x_goals=15.0,
                        goals_above_expected=5.0,
                        fenwick_pct=50.0,
                        corsi_pct=50.0,
                        points_per_game=1.0,
                    )
                ],
                free_agent_recommendations=[
                    AvailablePickup(
                        player_name="Missing FA Stats",
                        availability_type="FA",
                        stats_summary="Some stats here with enough characters to meet the minimum requirement for validation.",
                        pitch="This FA has 15.0 xGoals and 52% Fenwick with 5 games next week and good deployment on line 1. He's been unlucky with shooting and should see positive regression. The schedule is favorable for streaming opportunities.",
                        reasoning="Better xGoals (15.0 vs 12.0), Fenwick% (52% vs 48%), and schedule (5 games vs 3). Strong deployment with top linemates suggests continued opportunity.",
                        priority_level="strong_add",
                    )
                ],
                waiver_recommendations=[],
                summary="Summary with xGoals and Fenwick% analysis plus schedule considerations. Free agents can be added immediately for streaming.",
            )

    def test_summary_must_reference_stats_and_timing(self):
        """Summary validator should require both stats and FA/W timing."""
        # Missing stats (has timing but no stats)
        with pytest.raises(ValidationError, match="Summary must reference both advanced stats"):
            AvailablePlayersResponse(
                drop_candidates=[],
                player_stats=[
                    PlayerStats(
                        name="Test Player",
                        team="TOR",
                        position="C",
                        games_played=50,
                        goals=20,
                        assists=30,
                        points=50,
                        toi_per_game=18.0,
                        x_goals=15.0,
                        goals_above_expected=5.0,
                        fenwick_pct=50.0,
                        corsi_pct=50.0,
                        points_per_game=1.0,
                    )
                ],
                free_agent_recommendations=[],
                waiver_recommendations=[],
                summary="Free agents can be added immediately while waivers require a claim. Pick up these players now to improve your roster. The streaming opportunities are excellent for immediate adds.",
            )

        # Missing timing (has stats but no timing keywords like FA/waiver/claim/immediately/streaming)
        with pytest.raises(ValidationError, match="Summary must reference both advanced stats"):
            AvailablePlayersResponse(
                drop_candidates=[],
                player_stats=[
                    PlayerStats(
                        name="Test Player",
                        team="TOR",
                        position="C",
                        games_played=50,
                        goals=20,
                        assists=30,
                        points=50,
                        toi_per_game=18.0,
                        x_goals=15.0,
                        goals_above_expected=5.0,
                        fenwick_pct=50.0,
                        corsi_pct=50.0,
                        points_per_game=1.0,
                    )
                ],
                free_agent_recommendations=[],
                waiver_recommendations=[],
                summary="These players have strong xGoals and Fenwick% numbers with good schedules and many games coming soon. Add these to improve production.",
            )

    def test_valid_response(self):
        """Valid AvailablePlayersResponse should pass all validation."""
        response = AvailablePlayersResponse(
            drop_candidates=[
                DropCandidate(
                    player_name="Drop Player",
                    stats_summary="8 goals, 12 assists in 45 games. 3.2 GAE, 46.8% Fenwick.",
                    drop_rationale="Shooting above expected (3.2 GAE). Poor Fenwick% of 46.8. Light schedule with only 3 games.",
                )
            ],
            player_stats=[
                PlayerStats(
                    name="Drop Player",
                    team="TOR",
                    position="C",
                    games_played=45,
                    goals=8,
                    assists=12,
                    points=20,
                    toi_per_game=15.0,
                    x_goals=10.0,
                    goals_above_expected=3.2,
                    fenwick_pct=46.8,
                    corsi_pct=47.0,
                    points_per_game=0.44,
                ),
                PlayerStats(
                    name="FA Pickup",
                    team="MTL",
                    position="C",
                    games_played=50,
                    goals=15,
                    assists=20,
                    points=35,
                    toi_per_game=18.5,
                    x_goals=18.0,
                    goals_above_expected=-3.0,
                    fenwick_pct=52.0,
                    corsi_pct=51.5,
                    points_per_game=0.70,
                ),
            ],
            free_agent_recommendations=[
                AvailablePickup(
                    player_name="FA Pickup",
                    availability_type="FA",
                    stats_summary="15 goals, 20 assists in 50 games. 18.0 xGoals, 52% Fenwick. 5 games next week.",
                    pitch="FA Pickup has 18.0 xGoals but only 15 goals (-3.0 GAE), showing regression potential. Fenwick% of 52.0 indicates strong possession. Playing 18.5 min/game. Schedule: 5 games next 2 weeks vs Drop Player's 3 games.",
                    reasoning="Better xGoals (18.0 vs 10.0), Fenwick% (52% vs 46.8%), TOI (18.5 vs 15.0), and schedule (5 games vs 3). Negative GAE suggests positive regression.",
                    priority_level="strong_add",
                )
            ],
            waiver_recommendations=[],
            summary="Prioritize FA Pickup (free agent, immediate add) with strong xGoals (18.0) and Fenwick% (52.0). Drop Player is overperforming (3.2 GAE) with weak Fenwick% (46.8%). FA can be added immediately without waiver claim.",
        )
        assert len(response.player_stats) == 2
        assert len(response.free_agent_recommendations) == 1
        assert response.drop_candidates[0].player_name == "Drop Player"
