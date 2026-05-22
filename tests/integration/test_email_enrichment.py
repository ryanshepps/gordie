"""Tests for email enrichment with player statistics tables."""

from unittest.mock import patch

from agent.email_enrichment import (
    enrich_email_with_player_stats,
    extract_and_validate_player_names,
    fetch_player_stats,
    format_stats_table_html,
    format_stats_table_markdown,
)


def _mock_search_player(name):
    players = {
        "leon draisaitl": [
            {"name": "Leon Draisaitl", "player_id": 8477934, "team": "EDM", "position": "C"}
        ],
        "auston matthews": [
            {"name": "Auston Matthews", "player_id": 8479318, "team": "TOR", "position": "C"}
        ],
        "connor mcdavid": [
            {"name": "Connor McDavid", "player_id": 8478402, "team": "EDM", "position": "C"}
        ],
        "cale makar": [
            {"name": "Cale Makar", "player_id": 8480069, "team": "COL", "position": "D"}
        ],
        "nikita kucherov": [
            {"name": "Nikita Kucherov", "player_id": 8476453, "team": "TBL", "position": "RW"}
        ],
    }
    return players.get(name.lower(), [])


class TestExtractAndValidatePlayerNames:
    """Test player name extraction and validation."""

    def test_extracts_and_validates_full_names(self):
        """Should extract names and validate via CLI search."""
        with patch("agent.email_enrichment.search_player", side_effect=_mock_search_player):
            content = "I recommend picking up Leon Draisaitl and Auston Matthews."
            results = extract_and_validate_player_names(content)

            assert len(results) == 2
            assert ("Leon Draisaitl", 8477934) in results
            assert ("Auston Matthews", 8479318) in results

    def test_filters_non_players(self):
        """Should ignore extracted names that don't match any player."""
        with patch("agent.email_enrichment.search_player", side_effect=_mock_search_player):
            content = "Leon Draisaitl has great Power Play production."
            results = extract_and_validate_player_names(content)

            assert len(results) == 1
            assert ("Leon Draisaitl", 8477934) in results

    def test_handles_empty_content(self):
        """Should return empty list for empty content."""
        assert extract_and_validate_player_names("") == []

    def test_deduplicates_names(self):
        """Should only return each player once even if mentioned multiple times."""
        with patch("agent.email_enrichment.search_player", side_effect=_mock_search_player):
            content = "Leon Draisaitl is great. Leon Draisaitl scores again!"
            results = extract_and_validate_player_names(content)

            assert len(results) == 1

    def test_extracts_multiple_players(self):
        """Should extract and validate all player names from content."""
        with patch("agent.email_enrichment.search_player", side_effect=_mock_search_player):
            content = """
            Consider these players:
            - Auston Matthews has been on fire
            - Cale Makar is a top defenseman
            - Nikita Kucherov leads the league in points
            """
            results = extract_and_validate_player_names(content)

            assert len(results) == 3
            names = [name for name, _ in results]
            assert "Auston Matthews" in names
            assert "Cale Makar" in names
            assert "Nikita Kucherov" in names


class TestFormatStatsTableMarkdown:
    """Test markdown table formatting."""

    def test_returns_empty_string_for_no_stats(self):
        """Should return empty string when no stats provided."""
        result = format_stats_table_markdown([])
        assert result == ""

    def test_creates_valid_markdown_table(self):
        """Should create a properly formatted markdown table."""
        stats = [
            {
                "name": "Connor McDavid",
                "position": "C",
                "games_played": 30,
                "goals": 20,
                "assists": 35,
                "points": 55,
                "points_per_game": 1.83,
                "toi_per_game_minutes": 22.5,
                "x_goals": 15.5,
                "goals_above_expected": 4.5,
                "fenwick_pct": 55.2,
                "corsi_pct": 54.1,
                "shots_on_goal": 120,
                "high_danger_goals": 8,
            }
        ]
        result = format_stats_table_markdown(stats)

        assert "| Player |" in result
        assert "| --- |" in result
        assert "Connor McDavid" in result
        assert "**Player Statistics (via MoneyPuck)**" in result

    def test_handles_multiple_players(self):
        """Should format multiple players in the table."""
        stats = [
            {
                "name": "Player One",
                "position": "C",
                "games_played": 10,
                "goals": 5,
                "assists": 7,
                "points": 12,
                "points_per_game": 1.2,
                "toi_per_game_minutes": 18.5,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "fenwick_pct": 50.0,
                "corsi_pct": 51.0,
                "shots_on_goal": 40,
                "high_danger_goals": 2,
            },
            {
                "name": "Player Two",
                "position": "LW",
                "games_played": 10,
                "goals": 8,
                "assists": 4,
                "points": 12,
                "points_per_game": 1.2,
                "toi_per_game_minutes": 16.2,
                "x_goals": 6.0,
                "goals_above_expected": 2.0,
                "fenwick_pct": 48.0,
                "corsi_pct": 47.5,
                "shots_on_goal": 55,
                "high_danger_goals": 3,
            },
        ]
        result = format_stats_table_markdown(stats)
        assert "Player One" in result
        assert "Player Two" in result

    def test_table_structure_is_valid(self):
        """Should produce valid markdown table structure with correct row count."""
        stats = [
            {
                "name": f"Player {i}",
                "position": "C",
                "games_played": 10,
                "goals": i,
                "assists": i,
                "points": i * 2,
                "points_per_game": 1.0,
                "toi_per_game_minutes": 18.0,
                "x_goals": float(i),
                "goals_above_expected": 0.0,
                "fenwick_pct": 50.0,
                "corsi_pct": 50.0,
                "shots_on_goal": 30,
                "high_danger_goals": 1,
            }
            for i in range(1, 4)
        ]
        result = format_stats_table_markdown(stats)
        lines = [line for line in result.split("\n") if line.startswith("|")]
        assert len(lines) == 5


class TestFormatStatsTableHtml:
    """Test HTML table formatting."""

    def test_returns_empty_string_for_no_stats(self):
        """Should return empty string when no stats provided."""
        result = format_stats_table_html([])
        assert result == ""

    def test_creates_valid_html_table(self):
        """Should create a properly formatted HTML table."""
        stats = [
            {
                "name": "Connor McDavid",
                "position": "C",
                "games_played": 30,
                "goals": 20,
                "assists": 35,
                "points": 55,
                "points_per_game": 1.83,
                "toi_per_game_minutes": 22.5,
                "x_goals": 15.5,
                "goals_above_expected": 4.5,
                "fenwick_pct": 55.2,
                "corsi_pct": 54.1,
                "shots_on_goal": 120,
                "high_danger_goals": 8,
            }
        ]
        result = format_stats_table_html(stats)

        assert "<table" in result
        assert "</table>" in result
        assert "<thead>" in result
        assert "<tbody>" in result
        assert "Connor McDavid" in result
        assert "<details>" in result

    def test_includes_stats_legend(self):
        """Should include explanation of stat abbreviations."""
        stats = [
            {
                "name": "Test Player",
                "position": "C",
                "games_played": 10,
                "goals": 5,
                "assists": 5,
                "points": 10,
                "points_per_game": 1.0,
                "toi_per_game_minutes": 18.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "fenwick_pct": 50.0,
                "corsi_pct": 50.0,
                "shots_on_goal": 30,
                "high_danger_goals": 2,
            }
        ]
        result = format_stats_table_html(stats)
        assert "GP=Games Played" in result
        assert "xG=Expected Goals" in result


class TestFetchPlayerStats:
    """Test fetching stats by player name via CLI."""

    def test_returns_empty_for_no_names(self):
        """Should return empty list when no player names provided."""
        result = fetch_player_stats([])
        assert result == []

    def test_fetches_and_formats_stats(self):
        """Should fetch stats by name and format them correctly."""
        mock_stats = {
            "Connor McDavid": {
                "name": "Connor McDavid",
                "position": "C",
                "games_played": 30,
                "goals": 20,
                "points": 55,
                "points_per_game": 1.83,
                "toi_per_game_minutes": 22.5,
                "x_goals": 15.5,
                "fenwick_pct": 55.2,
                "corsi_pct": 54.1,
                "shots_on_goal": 120,
                "high_danger_goals": 8,
            }
        }

        with patch(
            "agent.email_enrichment.get_player_stats_by_names",
            return_value=mock_stats,
        ):
            result = fetch_player_stats(["Connor McDavid"])

        assert len(result) == 1
        stats = result[0]
        assert stats["name"] == "Connor McDavid"
        assert stats["goals"] == 20
        assert stats["points"] == 55
        assert stats["x_goals"] == 15.5
        assert stats["goals_above_expected"] == 4.5


class TestEnrichEmailWithPlayerStats:
    """Test the main enrichment pipeline."""

    def test_returns_empty_when_no_players_found(self):
        """Should return empty strings when no players in content."""
        with patch("agent.email_enrichment.search_player", return_value=[]):
            markdown, html = enrich_email_with_player_stats(
                message_content="No players mentioned here.",
                user_email="test@example.com",
                league_id="12345",
            )
        assert markdown == ""
        assert html == ""

    def test_returns_both_table_formats(self):
        """Should return both markdown and HTML tables."""
        mock_stats = {
            "Leon Draisaitl": {
                "name": "Leon Draisaitl",
                "position": "C",
                "games_played": 30,
                "goals": 20,
                "points": 55,
                "points_per_game": 1.83,
                "toi_per_game_minutes": 21.5,
                "x_goals": 15.5,
                "fenwick_pct": 55.2,
                "corsi_pct": 54.0,
                "shots_on_goal": 110,
                "high_danger_goals": 7,
            }
        }

        with (
            patch(
                "agent.email_enrichment.search_player",
                side_effect=_mock_search_player,
            ),
            patch(
                "agent.email_enrichment.get_player_stats_by_names",
                return_value=mock_stats,
            ),
        ):
            markdown, html = enrich_email_with_player_stats(
                message_content="Check out Leon Draisaitl!",
                user_email="test@example.com",
                league_id="12345",
            )

        assert markdown != ""
        assert html != ""
        assert "Leon Draisaitl" in markdown
        assert "Leon Draisaitl" in html

    def test_enrichment_includes_player_data(self):
        """Should include actual player data in enrichment output."""
        mock_stats = {
            "Leon Draisaitl": {
                "name": "Leon Draisaitl",
                "position": "C",
                "games_played": 30,
                "goals": 20,
                "points": 55,
                "points_per_game": 1.83,
                "toi_per_game_minutes": 21.5,
                "x_goals": 15.5,
                "fenwick_pct": 55.2,
                "corsi_pct": 54.0,
                "shots_on_goal": 110,
                "high_danger_goals": 7,
            },
            "Auston Matthews": {
                "name": "Auston Matthews",
                "position": "C",
                "games_played": 30,
                "goals": 18,
                "points": 48,
                "points_per_game": 1.6,
                "toi_per_game_minutes": 20.5,
                "x_goals": 14.0,
                "fenwick_pct": 54.5,
                "corsi_pct": 53.5,
                "shots_on_goal": 100,
                "high_danger_goals": 6,
            },
        }

        with (
            patch(
                "agent.email_enrichment.search_player",
                side_effect=_mock_search_player,
            ),
            patch(
                "agent.email_enrichment.get_player_stats_by_names",
                return_value=mock_stats,
            ),
        ):
            markdown, html = enrich_email_with_player_stats(
                message_content="Compare Leon Draisaitl and Auston Matthews",
                user_email="test@example.com",
                league_id="12345",
            )

        assert "Leon Draisaitl" in markdown
        assert "Auston Matthews" in markdown
        assert "Leon Draisaitl" in html
        assert "Auston Matthews" in html


class TestEmailEnrichmentIntegration:
    """Integration tests for the full enrichment flow."""

    def test_markdown_table_is_appendable_to_email(self):
        """Markdown table should start with newlines for appending."""
        stats = [
            {
                "name": "Test Player",
                "position": "C",
                "games_played": 10,
                "goals": 5,
                "assists": 5,
                "points": 10,
                "points_per_game": 1.0,
                "toi_per_game_minutes": 18.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "fenwick_pct": 50.0,
                "corsi_pct": 50.0,
                "shots_on_goal": 30,
                "high_danger_goals": 2,
            }
        ]
        result = format_stats_table_markdown(stats)
        assert result.startswith("\n\n")

    def test_html_table_is_appendable_to_email(self):
        """HTML table should have appropriate wrapper for appending."""
        stats = [
            {
                "name": "Test Player",
                "position": "C",
                "games_played": 10,
                "goals": 5,
                "assists": 5,
                "points": 10,
                "points_per_game": 1.0,
                "toi_per_game_minutes": 18.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "fenwick_pct": 50.0,
                "corsi_pct": 50.0,
                "shots_on_goal": 30,
                "high_danger_goals": 2,
            }
        ]
        result = format_stats_table_html(stats)
        assert "<div" in result
        assert "margin-top" in result
