"""Behavioral tests for weekly digest job.

These tests verify the observable behavior of the weekly digest system:
1. Digests are sent to opted-in users
2. Digests are NOT sent to opted-out users
3. Email content includes team name and league name
4. HTML includes unsubscribe footer
5. Performance data is categorized correctly
6. Free agents are enriched with stats

Testing philosophy: Capture outputs rather than suppress them.
Mock at boundaries only (database, email service, Yahoo API).
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from data.schemas import (
    CurrentMatchup,
    DigestData,
    EnrichedFreeAgent,
    PlayerPerformance,
    RosterPerformance,
    ScheduleTip,
)
from server.email_service import EmailResult


@pytest.fixture
def test_user():
    """Standard test user data."""
    return {"email": "test@example.com", "league_id": "12345", "team_id": "1"}


@pytest.fixture
def capture_email():
    """Capture emails instead of sending them.

    Returns a list that will contain all captured emails.
    Each email is a dict with: to, subject, text, html
    """
    sent_emails: list[dict[str, Any]] = []

    def capture_send(
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        **kwargs,
    ) -> EmailResult:
        sent_emails.append(
            {
                "to": to_email,
                "subject": subject,
                "text": text_body,
                "html": html_body,
            }
        )
        return EmailResult(success=True, message_id="test-123")

    with patch("scheduled.weekly_digest.EmailService") as mock_service_class:
        mock_instance = MagicMock()
        mock_instance.send_email.side_effect = capture_send
        mock_service_class.return_value = mock_instance
        yield sent_emails


@pytest.fixture
def mock_yahoo_roster():
    """Mock Yahoo API to return test roster data with player_points."""
    players = []
    player_data = [
        {
            "name": "Connor McDavid",
            "player_key": "nhl.p.6743",
            "player_id": "6743",
            "position": "C",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "status": None,
            "status_full": None,
            "points": 25.5,
        },
        {
            "name": "Leon Draisaitl",
            "player_key": "nhl.p.5017",
            "player_id": "5017",
            "position": "C",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "status": None,
            "status_full": None,
            "points": 22.0,
        },
        {
            "name": "Zach Hyman",
            "player_key": "nhl.p.5419",
            "player_id": "5419",
            "position": "LW",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "status": "IR",
            "status_full": "Injured Reserve",
            "points": 0.0,
        },
        {
            "name": "Bench Player",
            "player_key": "nhl.p.9999",
            "player_id": "9999",
            "position": "RW",
            "team": "EDM",
            "team_full": "Edmonton Oilers",
            "status": None,
            "status_full": None,
            "points": 2.0,
        },
    ]

    for data in player_data:
        player = SimpleNamespace(
            name=SimpleNamespace(full=data["name"]),
            player_key=data["player_key"],
            player_id=data["player_id"],
            display_position=data["position"],
            editorial_team_abbr=data["team"],
            editorial_team_full_name=data["team_full"],
            status=data["status"],
            status_full=data["status_full"],
            player_points=SimpleNamespace(total=data["points"]),
        )
        players.append(player)

    return players


@pytest.fixture
def mock_league_info():
    """Mock league info with current_week."""
    return SimpleNamespace(current_week=15)


@pytest.fixture
def mock_free_agents_response():
    """Mock response from search_available_players."""
    return json.dumps(
        {
            "players": [
                {"name": "Hot Player", "position": "C", "team": "TOR", "percent_owned": "45"},
                {"name": "Rising Star", "position": "LW", "team": "BOS", "percent_owned": "30"},
            ],
            "count": 2,
        }
    )


@pytest.fixture
def mock_comprehensive_stats_response():
    """Mock response from get_comprehensive_player_stats_internal."""
    return json.dumps(
        {
            "Hot Player": {
                "status": "success",
                "goals": 5,
                "assists": 8,
                "corsi_pct": 55.2,
                "games_remaining_this_week": 4,
            },
            "Rising Star": {
                "status": "success",
                "goals": 3,
                "assists": 4,
                "corsi_pct": 52.1,
                "games_remaining_this_week": 3,
            },
        }
    )


@pytest.fixture
def mock_schedule_response():
    """Mock response from get_team_schedule."""
    return json.dumps(
        {
            "EDM": {"status": "success", "this_week_games": 4, "next_week_games": 3},
            "TOR": {"status": "success", "this_week_games": 2, "next_week_games": 4},
        }
    )


@pytest.fixture
def mock_digest_dependencies(
    mock_yahoo_roster,
    mock_league_info,
    mock_free_agents_response,
    mock_comprehensive_stats_response,
    mock_schedule_response,
):
    """Mock all external dependencies for weekly digest."""
    # Mock notification preferences repository
    mock_pref_repo = MagicMock()

    # Mock league repository
    mock_league_repo = MagicMock()
    mock_league_repo.get_league.return_value = (
        "12345",  # league_id
        "nhl.l.12345",  # game_key
        "Test League",  # league_name
        "head",  # league_type
        json.dumps({"scoring_type": "head"}),  # league_settings
        "2024-01-01",  # created_at
    )

    # Mock team repository
    mock_team_repo = MagicMock()
    mock_team_repo.get_all.return_value = [
        (
            "12345",  # league_id
            "1",  # team_id
            "test@example.com",  # user_email
            "My Test Team",  # team_name
            "2024-01-01",  # created_at
        )
    ]

    # Mock Yahoo client
    mock_yahoo_client = MagicMock()
    mock_yahoo_client.query.get_team_roster_player_stats.return_value = mock_yahoo_roster
    mock_yahoo_client.query.get_team_roster_player_stats_by_week.return_value = mock_yahoo_roster
    mock_yahoo_client.query.get_league_info.return_value = mock_league_info

    # Mock email enrichment
    mock_enrichment = ("", "<table>Stats</table>")

    # Mock current matchup
    mock_matchup = CurrentMatchup(
        opponent_name="Rival Team",
        opponent_record="10-5-2",
        week=15,
        week_start="2025-01-06",
        week_end="2025-01-12",
    )

    patches = [
        patch(
            "scheduled.job_runner.NotificationPreferenceRepository",
            return_value=mock_pref_repo,
        ),
        patch(
            "scheduled.weekly_digest.YahooLeagueRepository",
            return_value=mock_league_repo,
        ),
        patch(
            "scheduled.weekly_digest.YahooUserTeamRepository",
            return_value=mock_team_repo,
        ),
        patch(
            "scheduled.weekly_digest.AuthenticatedYahooClient",
            return_value=mock_yahoo_client,
        ),
        patch(
            "scheduled.weekly_digest.enrich_email_with_player_stats",
            return_value=mock_enrichment,
        ),
        patch(
            "scheduled.weekly_digest.get_current_matchup",
            return_value=mock_matchup,
        ),
        patch(
            "scheduled.weekly_digest.search_available_players",
            **{"invoke.return_value": mock_free_agents_response},
        ),
        patch(
            "scheduled.weekly_digest.get_comprehensive_player_stats_internal",
            return_value=mock_comprehensive_stats_response,
        ),
        patch(
            "scheduled.weekly_digest.get_team_schedule",
            return_value=mock_schedule_response,
        ),
    ]

    for p in patches:
        p.start()

    yield {
        "pref_repo": mock_pref_repo,
        "yahoo_client": mock_yahoo_client,
    }

    for p in patches:
        p.stop()


class TestWeeklyDigestJob:
    """Test the weekly digest job behavior."""

    def test_digest_sent_to_opted_in_user(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Email is captured for user who should receive it."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1, "Expected exactly one email to be sent"
        assert capture_email[0]["to"] == test_user["email"]

    def test_digest_not_sent_to_opted_out_user(
        self,
        capture_email,
        mock_digest_dependencies,
    ):
        """No email captured for user who opted out."""
        from scheduled.weekly_digest import run_weekly_digest

        # Configure preference repo to return empty list (no opted-in users)
        mock_digest_dependencies["pref_repo"].get_all_enabled_for_type.return_value = []

        run_weekly_digest()

        assert len(capture_email) == 0, "No emails should be sent to opted-out users"

    def test_digest_content_includes_team_name(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Captured email text contains the team name."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1
        assert "My Test Team" in capture_email[0]["text"], (
            f"Team name not found in email body: {capture_email[0]['text'][:500]}"
        )

    def test_digest_content_includes_league_name(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Captured email subject contains league name."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1
        assert "Test League" in capture_email[0]["subject"], (
            f"League name not found in subject: {capture_email[0]['subject']}"
        )

    def test_digest_includes_unsubscribe_footer(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Captured HTML contains opt-out instructions."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1
        html_body = capture_email[0]["html"]
        assert html_body is not None, "HTML body should not be None"
        assert "stop receiving" in html_body.lower(), (
            f"Unsubscribe instructions not found in HTML: {html_body[:500]}"
        )

    def test_digest_includes_matchup_preview(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Captured email contains matchup preview."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1
        text = capture_email[0]["text"]
        assert "This Week's Matchup" in text
        assert "Rival Team" in text

    def test_digest_includes_performance_section(
        self,
        test_user,
        capture_email,
        mock_digest_dependencies,
    ):
        """Captured email contains last week's performance."""
        from scheduled.weekly_digest import send_digest

        send_digest(test_user["email"], test_user["league_id"])

        assert len(capture_email) == 1
        text = capture_email[0]["text"]
        assert "Last Week's Performance" in text
        assert "Top Performers" in text
        assert "Connor McDavid" in text


class TestDigestContent:
    """Test the digest content generation."""

    def test_build_digest_content_includes_performance(self):
        """Digest content includes roster performance information."""
        from scheduled.weekly_digest import build_digest_content

        data = DigestData(
            league_name="Test League",
            team_name="My Team",
            current_week=15,
            roster_performance=RosterPerformance(
                top_performers=[
                    PlayerPerformance(
                        name="Connor McDavid", position="C", nhl_team="EDM", points=25.5
                    ),
                    PlayerPerformance(
                        name="Leon Draisaitl", position="C", nhl_team="EDM", points=22.0
                    ),
                ],
                underperformers=[
                    PlayerPerformance(
                        name="Bench Player", position="RW", nhl_team="EDM", points=2.0
                    ),
                ],
                injured=[
                    PlayerPerformance(
                        name="Zach Hyman",
                        position="LW",
                        nhl_team="EDM",
                        points=0.0,
                        injury="Injured Reserve",
                    ),
                ],
            ),
        )

        content = build_digest_content(data)

        assert "## Last Week's Performance" in content
        assert "Connor McDavid" in content
        assert "25.5 pts" in content
        assert "Underperformers" in content
        assert "Injured Players" in content
        assert "Injured Reserve" in content

    def test_build_digest_content_includes_matchup(self):
        """Digest content includes matchup preview."""
        from scheduled.weekly_digest import build_digest_content

        data = DigestData(
            league_name="Test League",
            team_name="My Team",
            current_week=15,
            roster_performance=RosterPerformance(),
            current_matchup=CurrentMatchup(
                opponent_name="Rival Team",
                opponent_record="10-5-2",
                week=15,
                week_start="2025-01-06",
                week_end="2025-01-12",
            ),
        )

        content = build_digest_content(data)

        assert "## This Week's Matchup" in content
        assert "Rival Team" in content
        assert "10-5-2" in content

    def test_build_digest_content_includes_free_agents(self):
        """Digest content includes hot free agent recommendations."""
        from scheduled.weekly_digest import build_digest_content

        data = DigestData(
            league_name="Test League",
            team_name="My Team",
            current_week=15,
            roster_performance=RosterPerformance(),
            hot_free_agents=[
                EnrichedFreeAgent(
                    name="Hot Player",
                    position="C",
                    team="TOR",
                    percent_owned="45",
                    goals=5,
                    assists=8,
                    corsi_pct=55.2,
                    games_this_week=4,
                ),
            ],
        )

        content = build_digest_content(data)

        assert "## Recommendations" in content
        assert "Hot Free Agents" in content
        assert "Hot Player" in content
        assert "5G" in content
        assert "8A" in content
        assert "55.2% Corsi" in content

    def test_build_digest_content_includes_schedule_tips(self):
        """Digest content includes schedule-based tips."""
        from scheduled.weekly_digest import build_digest_content

        data = DigestData(
            league_name="Test League",
            team_name="My Team",
            current_week=15,
            roster_performance=RosterPerformance(),
            schedule_tips=[
                ScheduleTip(
                    team="EDM",
                    games_this_week=4,
                    player_names=["Connor McDavid", "Leon Draisaitl"],
                    tip_type="advantage",
                ),
                ScheduleTip(
                    team="TOR",
                    games_this_week=2,
                    player_names=["Mitch Marner"],
                    tip_type="warning",
                ),
            ],
        )

        content = build_digest_content(data)

        assert "Schedule Watch" in content
        assert "EDM has 4 games this week" in content
        assert "TOR only has 2 games" in content
        assert "consider benching" in content

    def test_build_digest_content_no_matchup(self):
        """Digest content works without matchup data."""
        from scheduled.weekly_digest import build_digest_content

        data = DigestData(
            league_name="Test League",
            team_name="My Team",
            current_week=15,
            roster_performance=RosterPerformance(),
            current_matchup=None,
        )

        content = build_digest_content(data)

        assert "This Week's Matchup" not in content
        assert "My Team" in content


class TestRosterPerformanceCategorization:
    """Test roster performance categorization logic."""

    def test_categorize_roster_separates_injured(self, mock_yahoo_roster):
        """Injured players are categorized separately."""
        from scheduled.weekly_digest import _categorize_roster_by_performance

        result = _categorize_roster_by_performance(mock_yahoo_roster, mock_yahoo_roster)

        injured_names = [p.name for p in result.injured]
        assert "Zach Hyman" in injured_names
        assert "Connor McDavid" not in injured_names

    def test_categorize_roster_sorts_by_points(self, mock_yahoo_roster):
        """Active players are sorted by points descending."""
        from scheduled.weekly_digest import _categorize_roster_by_performance

        result = _categorize_roster_by_performance(mock_yahoo_roster, mock_yahoo_roster)

        # Top performers should be sorted by points
        if len(result.top_performers) >= 2:
            assert result.top_performers[0].points >= result.top_performers[1].points


class TestDigestHtmlFormatting:
    """Test the HTML formatting functions via shared email_formatter module."""

    def test_format_email_converts_markdown_to_html(self):
        """Email formatter converts markdown to HTML."""
        from server.email_formatter import FooterType, format_email

        content = "## Header\n\n**Bold text** and *italic*"
        result = format_email(content, FooterType.NONE)

        assert "<h2>" in result.html_body
        assert "<strong>Bold text</strong>" in result.html_body
        assert "<em>italic</em>" in result.html_body

    def test_format_email_with_unsubscribe_footer(self):
        """Email formatter includes unsubscribe footer."""
        from server.email_formatter import FooterType, format_email

        content = "Test content"
        result = format_email(content, FooterType.UNSUBSCRIBE)

        assert "</body>" in result.html_body
        assert "</html>" in result.html_body
        assert "stop receiving" in result.html_body.lower()
        assert "stop receiving" in result.text_body.lower()


class TestPydanticModels:
    """Test Pydantic model behavior."""

    def test_matchup_opponent_record_property(self):
        """MatchupOpponent.record returns formatted string."""
        from data.schemas import MatchupOpponent

        opponent = MatchupOpponent(name="Test", team_key="nhl.t.1", wins=10, losses=5, ties=2)
        assert opponent.record == "10-5-2"

    def test_digest_data_defaults(self):
        """DigestData has proper default values."""
        data = DigestData(
            league_name="Test",
            team_name="Team",
            current_week=1,
            roster_performance=RosterPerformance(),
        )

        assert data.current_matchup is None
        assert data.hot_free_agents == []
        assert data.schedule_tips == []

    def test_enriched_free_agent_defaults(self):
        """EnrichedFreeAgent has proper default values."""
        fa = EnrichedFreeAgent(name="Test Player")

        assert fa.goals == 0
        assert fa.assists == 0
        assert fa.corsi_pct is None
        assert fa.games_this_week is None
