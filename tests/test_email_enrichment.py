"""Tests for email enrichment with player statistics tables.

These tests verify that:
- Player names are correctly extracted from email content
- Stats tables are generated in both markdown and HTML formats
- The enrichment pipeline produces valid output
"""

from unittest.mock import patch

import pandas as pd

from agent.email_enrichment import (
    enrich_email_with_player_stats,
    extract_player_names,
    fetch_player_stats,
    format_stats_table_html,
    format_stats_table_markdown,
    resolve_players_to_ids,
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
                "games_played": 30,
                "goals": 20,
                "primary_assists": 25,
                "secondary_assists": 10,
                "points": 55,
                "points_per_game": 1.83,
                "x_goals": 15.5,
                "goals_above_expected": 4.5,
                "pp_toi_per_game": 3.5,
                "fenwick_pct": 55.2,
            }
        ]
        result = format_stats_table_markdown(stats)

        # Should have header row
        assert "| Player |" in result
        assert "| Pos |" in result
        assert "| GP |" in result

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
                "games_played": 10,
                "goals": 5,
                "primary_assists": 5,
                "secondary_assists": 2,
                "points": 12,
                "points_per_game": 1.2,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "pp_toi_per_game": 2.0,
                "fenwick_pct": 50.0,
            },
            {
                "name": "Player Two",
                "position": "LW",
                "games_played": 10,
                "goals": 8,
                "primary_assists": 3,
                "secondary_assists": 1,
                "points": 12,
                "points_per_game": 1.2,
                "x_goals": 6.0,
                "goals_above_expected": 2.0,
                "pp_toi_per_game": 1.5,
                "fenwick_pct": 48.0,
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
                "primary_assists": i,
                "secondary_assists": 1,
                "points": i * 2 + 1,
                "points_per_game": 1.0,
                "x_goals": float(i),
                "goals_above_expected": 0.0,
                "pp_toi_per_game": 2.0,
                "fenwick_pct": 50.0,
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
                "games_played": 30,
                "goals": 20,
                "primary_assists": 25,
                "secondary_assists": 10,
                "points": 55,
                "points_per_game": 1.83,
                "x_goals": 15.5,
                "goals_above_expected": 4.5,
                "pp_toi_per_game": 3.5,
                "fenwick_pct": 55.2,
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
                "games_played": 10,
                "goals": 5,
                "primary_assists": 3,
                "secondary_assists": 2,
                "points": 10,
                "points_per_game": 1.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "pp_toi_per_game": 2.0,
                "fenwick_pct": 50.0,
            }
        ]
        result = format_stats_table_html(stats)
        assert "GP=Games Played" in result
        assert "xG=Expected Goals" in result


class TestResolvePlayersToIds:
    """Test player name to ID resolution."""

    def test_resolves_valid_player_names(self):
        """Should resolve player names to IDs via MoneyPuck search."""
        mock_df = pd.DataFrame(
            {
                "playerId": [8478402],
                "name": ["Connor McDavid"],
                "team": ["EDM"],
            }
        )

        with patch("agent.email_enrichment.search_players", return_value=mock_df):
            result = resolve_players_to_ids(["Connor McDavid"])

        assert len(result) == 1
        assert result[0]["player_id"] == 8478402
        assert result[0]["name"] == "Connor McDavid"

    def test_deduplicates_by_player_id(self):
        """Should not return duplicate player IDs."""
        mock_df = pd.DataFrame(
            {
                "playerId": [8478402],
                "name": ["Connor McDavid"],
                "team": ["EDM"],
            }
        )

        with patch("agent.email_enrichment.search_players", return_value=mock_df):
            # Same player searched twice
            result = resolve_players_to_ids(["Connor McDavid", "McDavid"])

        assert len(result) == 1

    def test_handles_not_found_players(self):
        """Should skip players that can't be found."""
        with patch("agent.email_enrichment.search_players", return_value=pd.DataFrame()):
            result = resolve_players_to_ids(["Nonexistent Player"])

        assert len(result) == 0


class TestFetchPlayerStats:
    """Test fetching stats from MoneyPuck."""

    def test_returns_empty_for_no_player_ids(self):
        """Should return empty list when no player IDs provided."""
        result = fetch_player_stats([])
        assert result == []

    def test_fetches_and_formats_stats(self):
        """Should fetch stats and format them correctly."""
        mock_all_df = pd.DataFrame(
            {
                "playerId": [8478402],
                "name": ["Connor McDavid"],
                "position": ["C"],
                "games_played": [30],
                "I_F_goals": [20],
                "I_F_primaryAssists": [25],
                "I_F_secondaryAssists": [10],
                "I_F_points": [55],
                "I_F_xGoals": [15.5],
                "onIce_fenwickPercentage": [0.552],
            }
        )
        mock_pp_df = pd.DataFrame(
            {
                "playerId": [8478402],
                "icetime": [6300.0],  # 105 minutes total
            }
        )

        with patch(
            "agent.email_enrichment.get_multiple_players_stats",
            side_effect=[mock_all_df, mock_pp_df],
        ):
            result = fetch_player_stats([8478402])

        assert len(result) == 1
        stats = result[0]
        assert stats["name"] == "Connor McDavid"
        assert stats["goals"] == 20
        assert stats["points"] == 55
        assert stats["x_goals"] == 15.5
        assert stats["goals_above_expected"] == 4.5  # 20 - 15.5


class TestEnrichEmailWithPlayerStats:
    """Test the main enrichment pipeline."""

    def test_returns_empty_when_no_players_found(self):
        """Should return empty strings when no players in content."""
        markdown, html = enrich_email_with_player_stats("No players mentioned here.")
        assert markdown == ""
        assert html == ""

    def test_returns_both_table_formats(self):
        """Should return both markdown and HTML tables."""
        mock_search_df = pd.DataFrame(
            {
                "playerId": [8477934],
                "name": ["Leon Draisaitl"],
                "team": ["EDM"],
            }
        )
        mock_all_df = pd.DataFrame(
            {
                "playerId": [8477934],
                "name": ["Leon Draisaitl"],
                "position": ["C"],
                "games_played": [30],
                "I_F_goals": [20],
                "I_F_primaryAssists": [25],
                "I_F_secondaryAssists": [10],
                "I_F_points": [55],
                "I_F_xGoals": [15.5],
                "onIce_fenwickPercentage": [0.552],
            }
        )
        mock_pp_df = pd.DataFrame(
            {
                "playerId": [8477934],
                "icetime": [6300.0],
            }
        )

        with (
            patch("agent.email_enrichment.search_players", return_value=mock_search_df),
            patch(
                "agent.email_enrichment.get_multiple_players_stats",
                side_effect=[mock_all_df, mock_pp_df],
            ),
        ):
            markdown, html = enrich_email_with_player_stats("Check out Leon Draisaitl!")

        assert markdown != ""
        assert html != ""
        assert "Leon Draisaitl" in markdown
        assert "Leon Draisaitl" in html

    def test_enrichment_includes_player_data(self):
        """Should include actual player data in enrichment output."""
        # search_players is called once per player name, so we need side_effect
        mock_search_draisaitl = pd.DataFrame(
            {"playerId": [8477934], "name": ["Leon Draisaitl"], "team": ["EDM"]}
        )
        mock_search_matthews = pd.DataFrame(
            {"playerId": [8479318], "name": ["Auston Matthews"], "team": ["TOR"]}
        )
        mock_all_df = pd.DataFrame(
            {
                "playerId": [8477934, 8479318],
                "name": ["Leon Draisaitl", "Auston Matthews"],
                "position": ["C", "C"],
                "games_played": [30, 30],
                "I_F_goals": [20, 18],
                "I_F_primaryAssists": [25, 22],
                "I_F_secondaryAssists": [10, 8],
                "I_F_points": [55, 48],
                "I_F_xGoals": [15.5, 14.0],
                "onIce_fenwickPercentage": [0.552, 0.545],
            }
        )
        mock_pp_df = pd.DataFrame(
            {
                "playerId": [8477934, 8479318],
                "icetime": [6300.0, 5400.0],
            }
        )

        with (
            patch(
                "agent.email_enrichment.search_players",
                side_effect=[mock_search_draisaitl, mock_search_matthews],
            ),
            patch(
                "agent.email_enrichment.get_multiple_players_stats",
                side_effect=[mock_all_df, mock_pp_df],
            ),
        ):
            markdown, html = enrich_email_with_player_stats(
                "Compare Leon Draisaitl and Auston Matthews"
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
                "games_played": 10,
                "goals": 5,
                "primary_assists": 3,
                "secondary_assists": 2,
                "points": 10,
                "points_per_game": 1.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "pp_toi_per_game": 2.0,
                "fenwick_pct": 50.0,
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
                "games_played": 10,
                "goals": 5,
                "primary_assists": 3,
                "secondary_assists": 2,
                "points": 10,
                "points_per_game": 1.0,
                "x_goals": 4.0,
                "goals_above_expected": 1.0,
                "pp_toi_per_game": 2.0,
                "fenwick_pct": 50.0,
            }
        ]
        result = format_stats_table_html(stats)
        # Should have container div
        assert "<div" in result
        assert "margin-top" in result  # Should have spacing
