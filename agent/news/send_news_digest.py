"""News digest job for sending personalized NHL news alerts.

This module orchestrates the daily news digest:
1. Fetches raw news from all sources (cached, shared across users)
2. Gets all users with news_digest notifications enabled
3. For each user, matches news against their roster
4. Sends personalized email if relevant alerts exist
"""

from __future__ import annotations

from agent.news.news_digest import NewsDigest, RawNewsCollection
from agent.news.news_processor import process_news_for_user
from client.authenticated_yahoo_client import AuthenticatedYahooClient
from client.news.espn_client import fetch_injuries
from client.news.matchup_client import fetch_matchups
from client.news.transactions_client import fetch_trades
from data.yahoo_league_repository import YahooLeagueRepository
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.logger import get_logger
from scheduled.job_runner import run_per_user_job
from server.email_formatter import FooterType, format_email
from server.email_service import EmailService

logger = get_logger(__name__)


def run_news_digest() -> None:
    """Send news digest emails to all opted-in users.

    This is the main entry point for the scheduled job.
    """
    # Fetch raw news from all sources (shared across all users)
    raw_news = _fetch_all_news()

    if not raw_news.injuries and not raw_news.trades and not raw_news.matchups:
        logger.info("No news items found from any source, skipping digest")
        return

    logger.info(
        f"Fetched raw news: {len(raw_news.injuries)} injuries, "
        f"{len(raw_news.trades)} trades, {len(raw_news.matchups)} matchups"
    )

    run_per_user_job(
        job_name="news_digest",
        notification_type="news_digest",
        handler=lambda email, league: _send_user_digest(raw_news, email, league),
    )


def _fetch_all_news() -> RawNewsCollection:
    """Fetch news from all sources and combine into a single collection.

    Returns:
        RawNewsCollection containing all alerts from all sources
    """
    injuries = fetch_injuries()
    trades = fetch_trades()
    matchups = fetch_matchups()

    return RawNewsCollection(
        injuries=injuries,
        trades=trades,
        matchups=matchups,
    )


def _send_user_digest(raw_news: RawNewsCollection, user_email: str, league_id: str) -> bool:
    """Process and send news digest to a single user for a specific league.

    Args:
        raw_news: Pre-fetched raw news collection
        user_email: User's email address
        league_id: Yahoo league ID

    Returns:
        True if email was sent, False if no relevant alerts (skipped)
    """
    # Fetch league info
    league_repo = YahooLeagueRepository()
    try:
        league = league_repo.get_league(league_id)
        if not league:
            logger.warning(f"League {league_id} not found, skipping digest for {user_email}")
            return False
        league_name = league[2]
    finally:
        league_repo.close()

    # Fetch user's team info
    team_repo = YahooUserTeamRepository()
    try:
        teams = team_repo.get_all(user_email=user_email, league_id=league_id)
        if not teams:
            logger.warning(f"No team found for {user_email} in league {league_id}")
            return False
        team_id = teams[0][1]
        team_name = teams[0][3]
    finally:
        team_repo.close()

    # Fetch current roster via Yahoo client
    yahoo_client = AuthenticatedYahooClient(user_email=user_email, league_id=int(league_id))
    current_roster = yahoo_client.query.get_team_roster_player_stats(team_id)

    # Process news against roster
    roster_list = (
        current_roster
        if isinstance(current_roster, list)
        else [current_roster] if current_roster else []
    )

    digest = process_news_for_user(
        raw_news=raw_news,
        roster=roster_list,
        user_email=user_email,
        league_id=league_id,
        team_id=team_id,
        league_name=league_name,
        team_name=team_name,
    )

    # Only send if there are relevant alerts
    if not digest.has_alerts():
        logger.debug(f"No relevant alerts for {user_email} in {league_name}")
        return False

    # Build email content
    content = build_digest_content(digest)

    # Format email
    email_content = format_email(
        content=content,
        footer_type=FooterType.UNSUBSCRIBE,
    )

    # Send email
    email_service = EmailService()
    result = email_service.send_email(
        to_email=user_email,
        subject=f"Daily NHL News - {league_name}",
        text_body=email_content.text_body,
        html_body=email_content.html_body,
    )

    if result.success:
        logger.info(f"Sent news digest to {user_email} for league {league_name}")
        return True
    else:
        logger.error(f"Failed to send digest to {user_email}: {result.error}")
        raise RuntimeError(f"Email send failed: {result.error}")


def build_digest_content(digest: NewsDigest) -> str:
    """Build the news digest email content in markdown format.

    Args:
        digest: NewsDigest containing user-specific alerts

    Returns:
        Markdown-formatted content for the email
    """
    sections: list[str] = []

    # Header
    sections.append(
        f"Hey there! Here's today's NHL news that affects your team "
        f"**{digest.team_name}** in {digest.league_name}."
    )
    sections.append("")

    # Injury Alerts
    if digest.injury_alerts:
        sections.append("## Injury Updates")
        sections.append("")
        for alert in digest.injury_alerts:
            sections.append(f"- **{alert.player_name}** ({alert.team}) - {alert.status}")
            if alert.description:
                sections.append(f"  - {alert.description}")
            sections.append(f"  - *{alert.fantasy_impact}*")
        sections.append("")

    # Trade Alerts
    if digest.trade_alerts:
        sections.append("## Trade News")
        sections.append("")
        for alert in digest.trade_alerts:
            sections.append(
                f"- **{alert.player_name}** traded from {alert.from_team} to {alert.to_team}"
            )
            sections.append(f"  - *{alert.fantasy_impact}*")
        sections.append("")

    # Matchup Alerts
    if digest.matchup_alerts:
        sections.append("## Favorable Matchups Today")
        sections.append("")
        sections.append(
            "These players face teams with high goals-against averages today:"
        )
        sections.append("")
        for alert in digest.matchup_alerts:
            sections.append(
                f"- **{alert.player_name}** vs {alert.opponent} "
                f"({alert.opponent_goals_against_avg:.2f} GAA) - consider starting"
            )
        sections.append("")

    # Footer with timestamp to ensure uniqueness
    sections.append("Good luck today!")
    sections.append("")
    sections.append(f"*- Gordie* | {digest.generated_at.strftime('%B %d, %Y at %I:%M %p')}")

    return "\n".join(sections)
