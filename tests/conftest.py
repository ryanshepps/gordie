"""Shared test fixtures for Gordie tests."""

import json

import pytest


@pytest.fixture
def sample_player_stats() -> dict[str, dict[str, object]]:
    """Sample player stats as returned by get_player_stats tool."""
    return {
        "8478402": {  # Connor McDavid
            "player_id": 8478402,
            "games_played": 10,
            "time_period": "last_10_games",
            "goals": 8,
            "assists": 15,
            "points": 23,
            "plus_minus": 12,
            "pim": 4,
            "hits": 5,
            "power_play_goals": 3,
            "sog": 45,
            "blocked_shots": 2,
            "shifts": 220,
            "giveaways": 8,
            "takeaways": 6,
            "corsi_for": 150,
            "fenwick_for": 120,
            "missed_shots": 15,
            "avg_faceoff_winning_pctg": 52.5,
            "goals_per_game": 0.8,
            "assists_per_game": 1.5,
            "points_per_game": 2.3,
            "sog_per_game": 4.5,
            "hits_per_game": 0.5,
        },
        "8477934": {  # Leon Draisaitl
            "player_id": 8477934,
            "games_played": 10,
            "time_period": "last_10_games",
            "goals": 6,
            "assists": 12,
            "points": 18,
            "plus_minus": 8,
            "pim": 6,
            "hits": 12,
            "power_play_goals": 2,
            "sog": 38,
            "blocked_shots": 4,
            "shifts": 210,
            "giveaways": 5,
            "takeaways": 4,
            "corsi_for": 140,
            "fenwick_for": 110,
            "missed_shots": 12,
            "avg_faceoff_winning_pctg": 55.0,
            "goals_per_game": 0.6,
            "assists_per_game": 1.2,
            "points_per_game": 1.8,
            "sog_per_game": 3.8,
            "hits_per_game": 1.2,
        },
    }


@pytest.fixture
def sample_player_stats_json(sample_player_stats) -> str:
    """Sample player stats as JSON string."""
    return json.dumps(sample_player_stats)


@pytest.fixture
def sample_fantasy_points() -> dict[str, dict[str, object]]:
    """Sample fantasy points as returned by calculate_fantasy_points tool."""
    return {
        "8478402": {
            "total_fantasy_points": 68.4,
            "breakdown": {
                "goals": 24.0,
                "assists": 30.0,
                "power_play_points": 3.0,
                "shots": 9.0,
                "hits": 1.0,
                "blocks": 0.4,
                "plus_minus": 6.0,
            },
            "games_played": 10,
            "fantasy_points_per_game": 6.84,
        },
        "8477934": {
            "total_fantasy_points": 52.0,
            "breakdown": {
                "goals": 18.0,
                "assists": 24.0,
                "power_play_points": 2.0,
                "shots": 7.6,
                "hits": 2.4,
                "blocks": 0.8,
                "plus_minus": 4.0,
            },
            "games_played": 10,
            "fantasy_points_per_game": 5.2,
        },
    }


@pytest.fixture
def sample_fantasy_points_json(sample_fantasy_points) -> str:
    """Sample fantasy points as JSON string."""
    return json.dumps(sample_fantasy_points)


@pytest.fixture
def defensive_player_stats() -> dict[str, dict[str, object]]:
    """Sample stats for a defenseman."""
    return {
        "8480069": {  # Cale Makar
            "player_id": 8480069,
            "games_played": 10,
            "time_period": "last_10_games",
            "goals": 3,
            "assists": 10,
            "points": 13,
            "plus_minus": 6,
            "pim": 2,
            "hits": 18,
            "power_play_goals": 1,
            "sog": 32,
            "blocked_shots": 15,
            "shifts": 250,
            "giveaways": 3,
            "takeaways": 5,
            "corsi_for": 160,
            "fenwick_for": 130,
            "missed_shots": 10,
            "avg_faceoff_winning_pctg": 0.0,
            "goals_per_game": 0.3,
            "assists_per_game": 1.0,
            "points_per_game": 1.3,
            "sog_per_game": 3.2,
            "hits_per_game": 1.8,
        },
    }
