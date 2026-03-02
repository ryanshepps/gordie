"""Evals for LLM-generated digest content.

Black-box evals that verify write_digest_content produces
output that:
1. References key data from the input (player names, team, league)
2. Stays within word limits
3. Doesn't leak raw JSON or system internals
4. Reads like Gordie's voice, not a system notification
"""

from datetime import datetime

import pytest

from agent.digest_writer import DigestType, write_digest_content
from agent.news.news_digest import (
    NewsDigest,
    UserInjuryAlert,
    UserMatchupAlert,
    UserTradeAlert,
)
from data.pydantic_models import (
    CurrentMatchup,
    DigestData,
    EnrichedFreeAgent,
    PlayerPerformance,
    RosterPerformance,
    ScheduleTip,
)
from tests.evals.conftest import retry_on_rate_limit

SYSTEM_LEAK_KEYWORDS = (
    "model_dump",
    "pydantic",
    "BaseModel",
    "system prompt",
    "gpt-4o",
    "langchain",
    "DigestData",
    "DigestType",
    "NewsDigest",
    "json",
)

TEMPLATE_KEYWORDS = (
    "here's your week",
    "hey there! here's",
    "good luck this week!",
    "## recommendations",
    "## last week's performance",
    "**top performers:**",
    "**underperformers",
    "**hot free agents",
)


@pytest.fixture
def weekly_digest_data():
    return DigestData(
        league_name="Northern Lights League",
        team_name="Maple Maulers",
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
                    name="Bench Warmer", position="RW", nhl_team="CBJ", points=1.0
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
        current_matchup=CurrentMatchup(
            opponent_name="Arctic Assassins",
            opponent_record="10-5-2",
            week=15,
            week_start="2025-01-06",
            week_end="2025-01-12",
        ),
        hot_free_agents=[
            EnrichedFreeAgent(
                name="Teuvo Teravainen",
                position="RW",
                team="CHI",
                percent_owned="45",
                goals=5,
                assists=8,
                corsi_pct=55.2,
                games_this_week=4,
            ),
        ],
        schedule_tips=[
            ScheduleTip(
                team="EDM",
                games_this_week=4,
                player_names=["Connor McDavid", "Leon Draisaitl"],
                tip_type="advantage",
            ),
        ],
    )


@pytest.fixture
def news_digest_data():
    return NewsDigest(
        user_email="test@example.com",
        league_id="12345",
        team_id="1",
        league_name="Northern Lights League",
        team_name="Maple Maulers",
        injury_alerts=[
            UserInjuryAlert(
                player_name="Zach Hyman",
                team="EDM",
                status="IR",
                description="Lower-body injury, out 4-6 weeks",
                fantasy_impact="Drop or stash on IR — he's done for the fantasy regular season.",
            ),
        ],
        trade_alerts=[
            UserTradeAlert(
                player_name="Mikko Rantanen",
                from_team="COL",
                to_team="CAR",
                trade_date="2025-01-15",
                fantasy_impact="Slight downgrade moving away from MacKinnon, but still a top-20 asset.",
            ),
        ],
        matchup_alerts=[
            UserMatchupAlert(
                player_name="Connor McDavid",
                opponent="CBJ",
                opponent_goals_against_avg=3.85,
                fantasy_impact="Smash start — Columbus is a sieve right now.",
            ),
        ],
        generated_at=datetime(2025, 1, 16, 8, 0),
    )


class TestWeeklyDigestContent:

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_top_performer(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        assert "mcdavid" in content_lower, (
            f"Expected top performer McDavid referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_matchup_opponent(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        assert "arctic assassins" in content_lower, (
            f"Expected matchup opponent referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_injured_player(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        assert "hyman" in content_lower, (
            f"Expected injured player Hyman referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_free_agent(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        assert "teravainen" in content_lower, (
            f"Expected free agent Teravainen referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_stays_within_word_limit(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        word_count = len(content.split())

        assert word_count <= 750, (
            f"Weekly digest exceeded word limit ({word_count} words, max 750): {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_no_system_leakage(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        for keyword in SYSTEM_LEAK_KEYWORDS:
            assert keyword.lower() not in content_lower, (
                f"System internals leaked into digest ({keyword}): {content[:500]}"
            )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_does_not_match_old_template(self, weekly_digest_data):
        content = write_digest_content(weekly_digest_data, DigestType.WEEKLY)
        content_lower = content.lower()

        for phrase in TEMPLATE_KEYWORDS:
            assert phrase not in content_lower, (
                f"Digest matches old template phrase '{phrase}': {content[:500]}"
            )


class TestNewsDigestContent:

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_injured_player(self, news_digest_data):
        content = write_digest_content(news_digest_data, DigestType.NEWS)
        content_lower = content.lower()

        assert "hyman" in content_lower, (
            f"Expected injured player Hyman referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_traded_player(self, news_digest_data):
        content = write_digest_content(news_digest_data, DigestType.NEWS)
        content_lower = content.lower()

        assert "rantanen" in content_lower, (
            f"Expected traded player Rantanen referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_references_matchup_alert(self, news_digest_data):
        content = write_digest_content(news_digest_data, DigestType.NEWS)
        content_lower = content.lower()

        assert "mcdavid" in content_lower, (
            f"Expected matchup alert player McDavid referenced: {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_stays_within_word_limit(self, news_digest_data):
        content = write_digest_content(news_digest_data, DigestType.NEWS)
        word_count = len(content.split())

        assert word_count <= 500, (
            f"News digest exceeded word limit ({word_count} words, max 500): {content[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_no_system_leakage(self, news_digest_data):
        content = write_digest_content(news_digest_data, DigestType.NEWS)
        content_lower = content.lower()

        for keyword in SYSTEM_LEAK_KEYWORDS:
            assert keyword.lower() not in content_lower, (
                f"System internals leaked into digest ({keyword}): {content[:500]}"
            )
