from __future__ import annotations

import uuid

from agent.channels.text_utils import strip_markdown
from agent.digest_writer import DigestType, write_digest_content
from agent.news.lineup_analyzer import analyze_lineup, parse_roster_position_configs
from agent.news.news_digest import RawNewsCollection
from agent.news.news_processor import _extract_roster_players, process_news_for_user
from agent.prompts.sport_context import get_digest_label
from client.authenticated_yahoo_client import AuthenticatedYahooClient
from client.news.espn_client import fetch_injuries
from client.news.matchup_client import fetch_matchups
from client.news.schedule_client import fetch_teams_playing_today
from client.news.transactions_client import fetch_trades
from data.digest_injury_state_repository import DigestInjuryStateRepository
from data.yahoo_league_repository import YahooLeagueRepository
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.logger import get_logger
from scheduled.channel_resolver import SmsDelivery, resolve_delivery_channel
from scheduled.job_runner import run_per_user_job
from server.email_formatter import FooterType, format_email
from server.email_service import EmailService
from server.sms_service import SmsService
from server.thread_manager import save_message_id_mapping

logger = get_logger(__name__)


def run_news_digest() -> None:
    raw_news = _fetch_all_news()

    if not raw_news.injuries and not raw_news.trades and not raw_news.matchups:
        logger.info("No news items found from any source, skipping digest")
        return

    logger.info(
        f"Fetched raw news: {len(raw_news.injuries)} injuries, "
        f"{len(raw_news.trades)} trades, {len(raw_news.matchups)} matchups"
    )

    teams_playing = fetch_teams_playing_today()

    run_per_user_job(
        job_name="news_digest",
        notification_type="news_digest",
        handler=lambda email, league: _send_user_digest(raw_news, email, league, teams_playing),
    )


def _fetch_all_news() -> RawNewsCollection:
    injuries = fetch_injuries()
    trades = fetch_trades()
    matchups = fetch_matchups()

    return RawNewsCollection(
        injuries=injuries,
        trades=trades,
        matchups=matchups,
    )


def _send_user_digest(
    raw_news: RawNewsCollection,
    user_email: str,
    league_id: str,
    teams_playing_today: set[str],
) -> bool:
    league_repo = YahooLeagueRepository()
    try:
        league = league_repo.get_league(league_id)
        if not league:
            logger.warning(f"League {league_id} not found, skipping digest for {user_email}")
            return False
        league_name = league[2]
        sport = league[3]
        league_settings_json = league[4]
    finally:
        league_repo.close()

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

    yahoo_client = AuthenticatedYahooClient(user_email=user_email, league_id=int(league_id))
    current_roster = yahoo_client.query.get_team_roster_player_stats(team_id)

    roster_list = (
        current_roster
        if isinstance(current_roster, list)
        else [current_roster] if current_roster else []
    )

    roster_players = _extract_roster_players(roster_list)

    roster_position_configs = parse_roster_position_configs(league_settings_json)
    lineup_analysis = analyze_lineup(roster_players, teams_playing_today, roster_position_configs)

    injury_state_repo = DigestInjuryStateRepository()
    try:
        previous_injury_states = injury_state_repo.get_previous_states(user_email)
    finally:
        injury_state_repo.close()

    digest = process_news_for_user(
        raw_news=raw_news,
        roster=roster_list,
        user_email=user_email,
        league_id=league_id,
        team_id=team_id,
        league_name=league_name,
        team_name=team_name,
        teams_playing_today=teams_playing_today,
        previous_injury_states=previous_injury_states,
        lineup_analysis=lineup_analysis,
    )

    if not digest.has_alerts():
        logger.debug(f"No relevant alerts for {user_email} in {league_name}")
        return False

    channel = resolve_delivery_channel(user_email)
    channel_key = "sms" if isinstance(channel, SmsDelivery) else "email"
    content = write_digest_content(digest, DigestType.NEWS, channel_key)

    digest_label = get_digest_label(sport)
    if isinstance(channel, SmsDelivery):
        _send_news_sms(content, channel.phone_number, user_email, league_name)
    else:
        _send_news_email(content, user_email, league_name, digest_label)

    current_injury_states = {
        alert.player_name.lower(): alert.status for alert in digest.injury_alerts
    }
    if current_injury_states:
        state_repo = DigestInjuryStateRepository()
        try:
            state_repo.save_current_states(user_email, current_injury_states)
        finally:
            state_repo.close()

    return True


def _send_news_email(content: str, user_email: str, league_name: str, digest_label: str = "NHL") -> None:
    email_content = format_email(
        content=content,
        footer_type=FooterType.UNSUBSCRIBE,
    )

    email_service = EmailService()
    result = email_service.send_email(
        to_email=user_email,
        subject=f"Daily {digest_label} News - {league_name}",
        text_body=email_content.text_body,
        html_body=email_content.html_body,
    )

    if result.success:
        if result.message_id:
            thread_id = f"{user_email}:{uuid.uuid4().hex[:12]}"
            save_message_id_mapping(
                message_id=result.message_id,
                thread_id=thread_id,
                user_email=user_email,
                subject=f"Daily {digest_label} News - {league_name}",
            )
        logger.info(f"Sent news digest to {user_email} for league {league_name}")
    else:
        logger.error(f"Failed to send digest to {user_email}: {result.error}")
        raise RuntimeError(f"Email send failed: {result.error}")


def _send_news_sms(
    content: str, phone_number: str, user_email: str, league_name: str
) -> None:
    plain_text = strip_markdown(content)
    sms_service = SmsService()
    result = sms_service.send_sms(phone_number, plain_text)

    if result.success:
        logger.info(f"Sent news digest SMS to {user_email} for league {league_name}")
    else:
        logger.error(f"Failed to send news digest SMS to {user_email}: {result.error}")
        raise RuntimeError(f"SMS send failed: {result.error}")

