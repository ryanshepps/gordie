"""Tests for email enrichment with player statistics tables.

These tests verify that:
- Player names are correctly extracted from email content
- Stats tables are generated in both markdown and HTML formats
- The enrichment pipeline produces valid output
"""

import json
from unittest.mock import patch

from agent.email_enrichment import (
    enrich_email_with_player_stats,
    extract_player_names,
    fetch_player_stats,
    format_stats_table_html,
    format_stats_table_markdown,
)


class TestExtractPlayerNames:
    """Test player name extraction from email content."""

    def test_extracts_full_names(self):
        """Should extract 'First Last' format names."""
        # Note: Names with mid-word capitals (e.g., McDavid) don't match the regex
        content = "I recommend picking up Leon Draisaitl and Auston Matthews."
        names = extract_player_names(content)
        assert "Leon Draisaitl" in names
        assert "Auston Matthews" in names

    def test_excludes_common_words(self):
        """Should not extract common words that look like names."""
        content = "The Team has Power Play time with Fantasy Hockey league."
        names = extract_player_names(content)
        assert len(names) == 0

    def test_handles_empty_content(self):
        """Should return empty list for empty content."""
        assert extract_player_names("") == []

    def test_deduplicates_names(self):
        """Should not return duplicate names."""
        content = "Leon Draisaitl is great. Leon Draisaitl scores again!"
        names = extract_player_names(content)
        assert names.count("Leon Draisaitl") == 1

    def test_extracts_multiple_players(self):
        """Should extract all player names from content."""
        content = """
        Consider these players:
        - Auston Matthews has been on fire
        - Cale Makar is a top defenseman
        - Nikita Kucherov leads the league in points
        """
        names = extract_player_names(content)
        assert len(names) == 3
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
                "estimated_line_number": "1",
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
                "yahoo_rank": "5",
            }
        ]
        result = format_stats_table_markdown(stats)

        # Should have header row
        assert "| Player |" in result
        assert "| Pos |" in result
        assert "| GP |" in result
        assert "| Line |" in result

        # Should have separator
        assert "| --- |" in result

        # Should have data
        assert "Connor McDavid" in result
        assert "20" in result  # goals

        # Should have title
        assert "**Player Statistics (via MoneyPuck)**" in result

    def test_handles_multiple_players(self):
        """Should format multiple players in the table."""
        stats = [
            {
                "name": "Player One",
                "position": "C",
                "estimated_line_number": "1",
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
                "yahoo_rank": "50",
            },
            {
                "name": "Player Two",
                "position": "LW",
                "estimated_line_number": "2",
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
                "yahoo_rank": "75",
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
                "estimated_line_number": str(i),
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
                "yahoo_rank": str(i * 10),
            }
            for i in range(1, 4)
        ]
        result = format_stats_table_markdown(stats)
        lines = [line for line in result.split("\n") if line.startswith("|")]
        # Header + separator + 3 data rows = 5 lines starting with |
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
                "estimated_line_number": "1",
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
                "yahoo_rank": "5",
            }
        ]
        result = format_stats_table_html(stats)

        # Should have table structure
        assert "<table" in result
        assert "</table>" in result
        assert "<thead>" in result
        assert "<tbody>" in result

        # Should have headers
        assert "<th" in result
        assert "Player" in result

        # Should have data
        assert "<td" in result
        assert "Connor McDavid" in result

        # Should have collapsible details
        assert "<details>" in result
        assert "<summary" in result

    def test_includes_stats_legend(self):
        """Should include explanation of stat abbreviations."""
        stats = [
            {
                "name": "Test Player",
                "position": "C",
                "estimated_line_number": "1",
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
                "yahoo_rank": "100",
            }
        ]
        result = format_stats_table_html(stats)
        assert "GP=Games Played" in result
        assert "xG=Expected Goals" in result
        assert "Line=Estimated Line" in result
        assert "TOI=Time On Ice" in result


class TestFetchPlayerStats:
    """Test fetching stats from comprehensive stats tool."""

    def test_returns_empty_for_no_player_names(self):
        """Should return empty list when no player names provided."""
        result = fetch_player_stats(
            player_names=[],
            user_email="test@example.com",
            league_id="12345",
        )
        assert result == []

    def test_fetches_and_formats_stats(self):
        """Should fetch stats and format them correctly."""
        mock_response = json.dumps(
            {
                "Connor McDavid": {
                    "status": "success",
                    "name": "Connor McDavid",
                    "position": "C",
                    "estimated_line_number": 1,
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
                    "yahoo_rank": 5,
                }
            }
        )

        with patch(
            "agent.email_enrichment.get_comprehensive_player_stats_internal",
            return_value=mock_response,
        ):
            result = fetch_player_stats(
                player_names=["Connor McDavid"],
                user_email="test@example.com",
                league_id="12345",
            )

        assert len(result) == 1
        stats = result[0]
        assert stats["name"] == "Connor McDavid"
        assert stats["goals"] == 20
        assert stats["points"] == 55
        assert stats["x_goals"] == 15.5
        assert stats["goals_above_expected"] == 4.5
        assert stats["estimated_line_number"] == "1"
        assert stats["yahoo_rank"] == "5"

    def test_handles_missing_line_and_rank(self):
        """Should display '-' for missing line number and yahoo rank."""
        mock_response = json.dumps(
            {
                "Test Player": {
                    "status": "success",
                    "name": "Test Player",
                    "position": "C",
                    "estimated_line_number": None,
                    "games_played": 10,
                    "goals": 5,
                    "assists": 5,
                    "points": 10,
                    "points_per_game": 1.0,
                    "toi_per_game_minutes": 15.0,
                    "x_goals": 4.0,
                    "goals_above_expected": 1.0,
                    "fenwick_pct": 50.0,
                    "corsi_pct": 50.0,
                    "shots_on_goal": 30,
                    "high_danger_goals": 2,
                    "yahoo_rank": None,
                }
            }
        )

        with patch(
            "agent.email_enrichment.get_comprehensive_player_stats_internal",
            return_value=mock_response,
        ):
            result = fetch_player_stats(
                player_names=["Test Player"],
                user_email="test@example.com",
                league_id="12345",
            )

        assert len(result) == 1
        assert result[0]["estimated_line_number"] == "-"
        assert result[0]["yahoo_rank"] == "-"


class TestEnrichEmailWithPlayerStats:
    """Test the main enrichment pipeline."""

    def test_returns_empty_when_no_players_found(self):
        """Should return empty strings when no players in content."""
        markdown, html = enrich_email_with_player_stats(
            message_content="No players mentioned here.",
            user_email="test@example.com",
            league_id="12345",
        )
        assert markdown == ""
        assert html == ""

    def test_returns_both_table_formats(self):
        """Should return both markdown and HTML tables."""
        mock_response = json.dumps(
            {
                "Leon Draisaitl": {
                    "status": "success",
                    "name": "Leon Draisaitl",
                    "position": "C",
                    "estimated_line_number": 1,
                    "games_played": 30,
                    "goals": 20,
                    "assists": 35,
                    "points": 55,
                    "points_per_game": 1.83,
                    "toi_per_game_minutes": 21.5,
                    "x_goals": 15.5,
                    "goals_above_expected": 4.5,
                    "fenwick_pct": 55.2,
                    "corsi_pct": 54.0,
                    "shots_on_goal": 110,
                    "high_danger_goals": 7,
                    "yahoo_rank": 3,
                }
            }
        )

        with patch(
            "agent.email_enrichment.get_comprehensive_player_stats_internal",
            return_value=mock_response,
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
        mock_response = json.dumps(
            {
                "Leon Draisaitl": {
                    "status": "success",
                    "name": "Leon Draisaitl",
                    "position": "C",
                    "estimated_line_number": 1,
                    "games_played": 30,
                    "goals": 20,
                    "assists": 35,
                    "points": 55,
                    "points_per_game": 1.83,
                    "toi_per_game_minutes": 21.5,
                    "x_goals": 15.5,
                    "goals_above_expected": 4.5,
                    "fenwick_pct": 55.2,
                    "corsi_pct": 54.0,
                    "shots_on_goal": 110,
                    "high_danger_goals": 7,
                    "yahoo_rank": 3,
                },
                "Auston Matthews": {
                    "status": "success",
                    "name": "Auston Matthews",
                    "position": "C",
                    "estimated_line_number": 1,
                    "games_played": 30,
                    "goals": 18,
                    "assists": 30,
                    "points": 48,
                    "points_per_game": 1.6,
                    "toi_per_game_minutes": 20.5,
                    "x_goals": 14.0,
                    "goals_above_expected": 4.0,
                    "fenwick_pct": 54.5,
                    "corsi_pct": 53.5,
                    "shots_on_goal": 100,
                    "high_danger_goals": 6,
                    "yahoo_rank": 8,
                },
            }
        )

        with patch(
            "agent.email_enrichment.get_comprehensive_player_stats_internal",
            return_value=mock_response,
        ):
            markdown, html = enrich_email_with_player_stats(
                message_content="Compare Leon Draisaitl and Auston Matthews",
                user_email="test@example.com",
                league_id="12345",
            )

        # Both players should be in output
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
                "estimated_line_number": "2",
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
                "yahoo_rank": "100",
            }
        ]
        result = format_stats_table_markdown(stats)
        # Should start with newlines for clean appending
        assert result.startswith("\n\n")

    def test_html_table_is_appendable_to_email(self):
        """HTML table should have appropriate wrapper for appending."""
        stats = [
            {
                "name": "Test Player",
                "position": "C",
                "estimated_line_number": "2",
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
                "yahoo_rank": "100",
            }
        ]
        result = format_stats_table_html(stats)
        # Should have container div
        assert "<div" in result
        assert "margin-top" in result  # Should have spacing
