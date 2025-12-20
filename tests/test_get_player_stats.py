"""Tests for player stats retrieval feature.

These tests verify that player statistics are correctly fetched and aggregated
from the NHL stats database. Tests focus on:
- Correct aggregation for different time periods
- Per-game averages
- Handling of missing data
- Multiple player queries
"""

import json
from unittest.mock import MagicMock, patch

from tools.player_comparison.get_player_stats import get_player_stats


def create_mock_game_row(
    player_id: int,
    game_id: int,
    game_date: str,
    goals: int = 0,
    assists: int = 0,
    points: int = 0,
    plus_minus: int = 0,
    pim: int = 0,
    hits: int = 0,
    power_play_goals: int = 0,
    sog: int = 0,
    faceoff_pct: float = 0.0,
    toi: str = "20:00",
    blocked_shots: int = 0,
    shifts: int = 20,
    giveaways: int = 0,
    takeaways: int = 0,
    corsi_for: int = 0,
    fenwick_for: int = 0,
    missed_shots: int = 0,
) -> tuple[object, ...]:
    """Create a mock game row matching the database schema."""
    return (
        player_id,  # 0: nhl_api_player_id
        game_id,  # 1: nhl_api_game_id
        game_date,  # 2: game_date
        "Test Player",  # 3: full_name
        "Test",  # 4: first_name
        "Player",  # 5: last_name
        goals,  # 6: goals
        assists,  # 7: assists
        points,  # 8: points
        plus_minus,  # 9: plus_minus
        pim,  # 10: pim
        hits,  # 11: hits
        power_play_goals,  # 12: power_play_goals
        sog,  # 13: sog
        faceoff_pct,  # 14: faceoff_winning_pctg
        toi,  # 15: toi
        blocked_shots,  # 16: blocked_shots
        shifts,  # 17: shifts
        giveaways,  # 18: giveaways
        takeaways,  # 19: takeaways
        corsi_for,  # 20: corsi_for
        fenwick_for,  # 21: fenwick_for
        missed_shots,  # 22: missed_shots
    )


class TestStatAggregation:
    """Test that stats are correctly aggregated across games."""

    def test_sums_goals_across_games(self):
        """Total goals should sum across all games in period."""
        mock_games = [
            create_mock_game_row(8478402, 1, "2024-01-01", goals=2),
            create_mock_game_row(8478402, 2, "2024-01-03", goals=1),
            create_mock_game_row(8478402, 3, "2024-01-05", goals=3),
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        assert result["8478402"]["goals"] == 6

    def test_sums_all_counting_stats(self):
        """All counting stats should be summed correctly."""
        mock_games = [
            create_mock_game_row(
                8478402,
                1,
                "2024-01-01",
                goals=2,
                assists=1,
                points=3,
                hits=3,
                sog=5,
                blocked_shots=1,
            ),
            create_mock_game_row(
                8478402,
                2,
                "2024-01-03",
                goals=1,
                assists=2,
                points=3,
                hits=2,
                sog=4,
                blocked_shots=2,
            ),
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        stats = result["8478402"]
        assert stats["goals"] == 3
        assert stats["assists"] == 3
        assert stats["points"] == 6
        assert stats["hits"] == 5
        assert stats["sog"] == 9
        assert stats["blocked_shots"] == 3

    def test_sums_plus_minus_correctly(self):
        """Plus/minus should sum including negative values."""
        mock_games = [
            create_mock_game_row(8478402, 1, "2024-01-01", plus_minus=3),
            create_mock_game_row(8478402, 2, "2024-01-03", plus_minus=-2),
            create_mock_game_row(8478402, 3, "2024-01-05", plus_minus=1),
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        assert result["8478402"]["plus_minus"] == 2  # 3 - 2 + 1


class TestPerGameAverages:
    """Test that per-game averages are calculated correctly."""

    def test_calculates_points_per_game(self):
        """Points per game should be total points / games played."""
        mock_games = [
            create_mock_game_row(8478402, 1, "2024-01-01", points=3),
            create_mock_game_row(8478402, 2, "2024-01-03", points=2),
            create_mock_game_row(8478402, 3, "2024-01-05", points=4),
            create_mock_game_row(8478402, 4, "2024-01-07", points=1),
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        assert result["8478402"]["points_per_game"] == 2.5  # 10 points / 4 games

    def test_calculates_all_per_game_averages(self):
        """Should calculate per-game averages for goals, assists, sog, hits."""
        mock_games = [
            create_mock_game_row(
                8478402, 1, "2024-01-01", goals=2, assists=1, sog=5, hits=3
            ),
            create_mock_game_row(
                8478402, 2, "2024-01-03", goals=0, assists=3, sog=3, hits=1
            ),
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        stats = result["8478402"]
        assert stats["goals_per_game"] == 1.0  # 2 / 2
        assert stats["assists_per_game"] == 2.0  # 4 / 2
        assert stats["sog_per_game"] == 4.0  # 8 / 2
        assert stats["hits_per_game"] == 2.0  # 4 / 2


class TestTimePeriods:
    """Test that different time periods are handled correctly."""

    def test_last_5_games_limits_results(self):
        """last_5_games should only use 5 most recent games."""
        # Create 10 games but expect only 5 to be used
        mock_games = [
            create_mock_game_row(8478402, i, f"2024-01-{i:02d}", goals=1)
            for i in range(1, 6)
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_5_games"}
                )
            )

        assert result["8478402"]["games_played"] == 5

    def test_season_includes_all_games(self):
        """season period should include all available games."""
        mock_games = [
            create_mock_game_row(8478402, i, f"2024-{(i % 12) + 1:02d}-01", goals=1)
            for i in range(1, 51)  # 50 games
        ]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "season"}
                )
            )

        assert result["8478402"]["games_played"] == 50

    def test_returns_time_period_in_response(self):
        """Response should include which time period was used."""
        mock_games = [create_mock_game_row(8478402, 1, "2024-01-01", goals=1)]

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = (
                mock_games
            )

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_20_games"}
                )
            )

        assert result["8478402"]["time_period"] == "last_20_games"


class TestMultiplePlayersQuery:
    """Test querying stats for multiple players at once."""

    def test_returns_stats_for_all_players(self):
        """Should return stats for each player in the input list."""
        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            # Return different data for each player query
            def mock_execute(query, params):
                mock_result = MagicMock()
                player_id = params[0]
                if player_id == 8478402:
                    mock_result.fetchall.return_value = [
                        create_mock_game_row(8478402, 1, "2024-01-01", goals=3)
                    ]
                elif player_id == 8477934:
                    mock_result.fetchall.return_value = [
                        create_mock_game_row(8477934, 1, "2024-01-01", goals=2)
                    ]
                else:
                    mock_result.fetchall.return_value = []
                return mock_result

            mock_repo.return_value.conn.execute.side_effect = mock_execute

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402, 8477934], "time_period": "last_10_games"}
                )
            )

        assert "8478402" in result
        assert "8477934" in result
        assert result["8478402"]["goals"] == 3
        assert result["8477934"]["goals"] == 2


class TestNoDataHandling:
    """Test handling of players with no stats."""

    def test_returns_no_data_status_for_missing_player(self):
        """Should return no_data status when player has no games."""
        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = []

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [9999999], "time_period": "last_10_games"}
                )
            )

        assert result["9999999"]["status"] == "no_data"

    def test_handles_mix_of_found_and_missing_players(self):
        """Should handle some players having data and others not."""
        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:

            def mock_execute(query, params):
                mock_result = MagicMock()
                player_id = params[0]
                if player_id == 8478402:
                    mock_result.fetchall.return_value = [
                        create_mock_game_row(8478402, 1, "2024-01-01", goals=3)
                    ]
                else:
                    mock_result.fetchall.return_value = []
                return mock_result

            mock_repo.return_value.conn.execute.side_effect = mock_execute

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402, 9999999], "time_period": "last_10_games"}
                )
            )

        assert result["8478402"]["goals"] == 3
        assert result["9999999"]["status"] == "no_data"


class TestNullStatHandling:
    """Test handling of null/None values in stats."""

    def test_treats_null_stats_as_zero(self):
        """Null stat values should be treated as 0."""
        # Create a row with None values (simulating database NULLs)
        null_game = (
            8478402,
            1,
            "2024-01-01",
            "Test Player",
            "Test",
            "Player",
            None,  # goals
            None,  # assists
            None,  # points
            None,  # plus_minus
            None,  # pim
            None,  # hits
            None,  # power_play_goals
            None,  # sog
            None,  # faceoff_pct
            None,  # toi
            None,  # blocked_shots
            None,  # shifts
            None,  # giveaways
            None,  # takeaways
            None,  # corsi_for
            None,  # fenwick_for
            None,  # missed_shots
        )

        with patch(
            "tools.player_comparison.get_player_stats.NHLPlayerStatsRepository"
        ) as mock_repo:
            mock_repo.return_value.conn.execute.return_value.fetchall.return_value = [
                null_game
            ]

            result = json.loads(
                get_player_stats.invoke(
                    {"player_ids": [8478402], "time_period": "last_10_games"}
                )
            )

        stats = result["8478402"]
        assert stats["goals"] == 0
        assert stats["assists"] == 0
        assert stats["points"] == 0

