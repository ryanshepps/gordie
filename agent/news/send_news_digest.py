from __future__ import annotations

import uuid
from collections import defaultdict

from agent.channels.text_utils import strip_markdown
from agent.context_types import Sport
from agent.digest_writer import DigestType, write_digest_content
from agent.news.lineup_analyzer import analyze_lineup, parse_roster_position_configs
from agent.news.news_digest import RawNewsCollection
from agent.news.news_processor import _extract_roster_players, process_news_for_user
from agent.prompts.sport_context import get_digest_label
from client.authenticated_yahoo_client import AuthenticatedYahooClient
from client.news.sport_clients import get_news_clients
from data.digest_injury_state_repository import DigestInjuryStateRepository
from data.notification_preference_repository import NotificationPreferenceRepository
from data.yahoo_league_repository import YahooLeagueRepository
from data.yahoo_user_team_repository import YahooUserTeamRepository
from module.logger import get_logger
from scheduled.channel_resolver import SmsDelivery, resolve_delivery_channel
from scheduled.job_runner import JobResult, _record_digest_delivery, is_user_eligible_for_digest
from server.email_formatter import FooterType, format_email
from server.email_service import EmailService
from server.sms_service import SmsService
from server.thread_manager import save_message_id_mapping

logger = get_logger(__name__)


def run_news_digest() -> None:
    repo = NotificationPreferenceRepository()
    try:
        user_leagues = repo.get_all_enabled_for_type("news_digest")
    finally:
        repo.close()

    if not user_leagues:
        logger.info("No users opted in for news_digest")
        return

    grouped = _group_by_sport(user_leagues)

    result = JobResult()
    for sport, pairs in grouped.items():
        _process_sport_group(sport, pairs, result)

    logger.info(
        f"news_digest complete: {result.success} sent, "
        f"{result.skipped} skipped, {result.failed} failed"
    )


def _group_by_sport(
    user_leagues: list[tuple[str, str]],
) -> dict[Sport, list[tuple[str, str]]]:
    league_repo = YahooLeagueRepository()
    try:
        grouped: dict[Sport, list[tuple[str, str]]] = defaultdict(list)
        for user_email, league_id in user_leagues:
            league = league_repo.get_league(league_id)
            if not league:
                continue
            sport: Sport = league[3] or "nhl"
            grouped[sport].append((user_email, league_id))
        return dict(grouped)
    finally:
        league_repo.close()


def _process_sport_group(
    sport: Sport,
    pairs: list[tuple[str, str]],
    result: JobResult,
) -> None:
    try:
        clients = get_news_clients(sport)
    except ValueError:
        logger.warning(f"No news clients for sport {sport}, skipping {len(pairs)} users")
        result.skipped += len(pairs)
        return

    raw_news = RawNewsCollection(
        injuries=clients.fetch_injuries(),
        trades=clients.fetch_trades(),
        matchups=clients.fetch_matchups(),
    )

    if not raw_news.injuries and not raw_news.trades and not raw_news.matchups:
        logger.info(f"No {sport} news items found, skipping {len(pairs)} users")
        result.skipped += len(pairs)
        return

    logger.info(
        f"Fetched {sport} news: {len(raw_news.injuries)} injuries, "
        f"{len(raw_news.trades)} trades, {len(raw_news.matchups)} matchups"
    )

    teams_playing = clients.fetch_teams_playing_today()

    for user_email, league_id in pairs:
        if not is_user_eligible_for_digest(user_email):
            result.skipped += 1
            continue

        try:
            sent = _send_user_digest(raw_news, user_email, league_id, teams_playing, sport)
            if sent:
                result.success += 1
                _record_digest_delivery(user_email)
            else:
                result.skipped += 1
        except Exception as e:
            result.failed += 1
            logger.error(f"news_digest failed for {user_email}/{league_id}: {e}")


def _send_user_digest(
    raw_news: RawNewsCollection,
    user_email: str,
    league_id: str,
    teams_playing_today: set[str],
    sport: Sport = "nhl",
) -> bool:
    league_repo = YahooLeagueRepository()
    try:
        league = league_repo.get_league(league_id)
        if not league:
            logger.warning(f"League {league_id} not found, skipping digest for {user_email}")
            return False
        league_name = league[2]
        league_settings_json = league[4]
    finally:
        league_repo.close()

    team_repo = YahooUserTeamRepository()
    try:
        teams = team_repo.get_user_teams_for_league(user_email, league_id)
        if not teams:
            logger.warning(f"No team found for {user_email} in league {league_id}")
            return False
        team_id = teams[0][1]
        team_name = teams[0][3]
    finally:
        team_repo.close()

    yahoo_client = AuthenticatedYahooClient(
        user_email=user_email,
        league_id=int(league_id),
        game_code=sport,
    )
    current_roster = yahoo_client.query.get_team_roster_player_stats(team_id)

    roster_list = (
        current_roster
        if isinstance(current_roster, list)
        else [current_roster]
        if current_roster
        else []
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


def _send_news_email(
    content: str, user_email: str, league_name: str, digest_label: str = "NHL"
) -> None:
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


def _send_news_sms(content: str, phone_number: str, user_email: str, league_name: str) -> None:
    plain_text = strip_markdown(content)
    sms_service = SmsService()
    result = sms_service.send_sms(phone_number, plain_text)

    if result.success:
        logger.info(f"Sent news digest SMS to {user_email} for league {league_name}")
    else:
        logger.error(f"Failed to send news digest SMS to {user_email}: {result.error}")
        raise RuntimeError(f"SMS send failed: {result.error}")
