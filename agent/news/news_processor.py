from __future__ import annotations

from collections.abc import Sequence

from agent.news.lineup_analyzer import LineupAnalysis
from agent.news.news_digest import (
    InjuryAlert,
    MatchupAlert,
    NewsDigest,
    RawNewsCollection,
    RosterPlayer,
    TradeAlert,
    UserInjuryAlert,
    UserMatchupAlert,
    UserTradeAlert,
)
from module.logger import get_logger

logger = get_logger(__name__)

YahooPlayer = object


def process_news_for_user(
    raw_news: RawNewsCollection,
    roster: Sequence[YahooPlayer],
    user_email: str,
    league_id: str,
    team_id: str,
    league_name: str,
    team_name: str,
    teams_playing_today: set[str] | None = None,
    previous_injury_states: dict[str, str] | None = None,
    lineup_analysis: LineupAnalysis | None = None,
) -> NewsDigest:
    roster_players = _extract_roster_players(roster)
    roster_names = {p.name for p in roster_players}

    logger.debug(f"Processing news for {user_email} with {len(roster_names)} rostered players")

    playing_today = teams_playing_today or set()
    prev_states = previous_injury_states or {}

    roster_by_name = {p.name: p for p in roster_players}

    injury_alerts = _match_injury_alerts(
        raw_news.injuries, roster_names, roster_by_name, playing_today, prev_states
    )
    trade_alerts = _match_trade_alerts(raw_news.trades, roster_names)
    matchup_alerts = _match_matchup_alerts(raw_news.matchups, roster_names, lineup_analysis)

    bench_reminders: list[str] = []
    position_conflicts: dict[str, list[str]] = {}
    if lineup_analysis:
        bench_reminders = lineup_analysis.benched_players_with_games
        position_conflicts = lineup_analysis.position_conflicts

    digest = NewsDigest(
        user_email=user_email,
        league_id=league_id,
        team_id=team_id,
        league_name=league_name,
        team_name=team_name,
        injury_alerts=injury_alerts,
        trade_alerts=trade_alerts,
        matchup_alerts=matchup_alerts,
        bench_reminders=bench_reminders,
        position_conflicts=position_conflicts,
    )

    logger.info(
        f"Generated digest for {user_email}: "
        f"{len(injury_alerts)} injuries, {len(trade_alerts)} trades, "
        f"{len(matchup_alerts)} matchups, {len(bench_reminders)} bench reminders"
    )

    return digest


def _extract_roster_players(roster: Sequence[YahooPlayer]) -> list[RosterPlayer]:
    players: list[RosterPlayer] = []

    items = roster if isinstance(roster, list) else [roster] if roster else []

    for player in items:
        name_obj = getattr(player, "name", None)
        name = ""
        if name_obj:
            if hasattr(name_obj, "full"):
                name = str(name_obj.full).lower()
            elif hasattr(name_obj, "first") and hasattr(name_obj, "last"):
                name = f"{name_obj.first} {name_obj.last}".lower()
            else:
                name = str(name_obj).lower()

        if not name:
            continue

        nhl_team = str(getattr(player, "editorial_team_abbr", "") or "").upper()
        roster_slot = str(getattr(player, "selected_position_value", "") or "")
        position = str(getattr(player, "display_position", "") or "")

        players.append(
            RosterPlayer(
                name=name,
                nhl_team=nhl_team,
                roster_slot=roster_slot,
                position=position,
            )
        )

    return players


def _normalize_name(name: str) -> str:
    return name.lower().strip()


def _names_match(roster_name: str, alert_name: str) -> bool:
    alert_normalized = _normalize_name(alert_name)

    if roster_name == alert_normalized:
        return True

    roster_clean = roster_name.replace(".", "").replace("-", " ")
    alert_clean = alert_normalized.replace(".", "").replace("-", " ")

    if roster_clean == alert_clean:
        return True

    roster_parts = roster_clean.split()
    alert_parts = alert_clean.split()

    if len(alert_parts) == 1 and len(roster_parts) >= 2 and roster_parts[-1] == alert_parts[0]:
        return True

    if len(roster_parts) >= 2 and len(alert_parts) >= 2:
        last_names_match = roster_parts[-1] == alert_parts[-1]
        first_initial_match = roster_parts[0][0] == alert_parts[0][0]
        return last_names_match and first_initial_match

    return False


def _match_injury_alerts(
    injuries: list[InjuryAlert],
    roster_names: set[str],
    roster_by_name: dict[str, RosterPlayer],
    teams_playing_today: set[str],
    previous_injury_states: dict[str, str],
) -> list[UserInjuryAlert]:
    matched: list[UserInjuryAlert] = []

    for injury in injuries:
        for roster_name in roster_names:
            if _names_match(roster_name, injury.player_name):
                roster_player = roster_by_name.get(roster_name)
                has_game_today = (
                    roster_player.nhl_team in teams_playing_today if roster_player else False
                )
                is_new = (
                    roster_name not in previous_injury_states
                    or previous_injury_states[roster_name] != injury.status
                )
                already_on_ir_slot = (
                    roster_player.roster_slot in ("IR", "IR+") if roster_player else False
                )

                if not is_new and not has_game_today:
                    break

                fantasy_impact = _generate_injury_impact(
                    injury, has_game_today, is_new, already_on_ir_slot
                )

                matched.append(
                    UserInjuryAlert(
                        player_name=injury.player_name,
                        team=injury.team,
                        status=injury.status,
                        description=injury.description,
                        fantasy_impact=fantasy_impact,
                        has_game_today=has_game_today,
                        is_new_injury=is_new,
                        already_on_ir_slot=already_on_ir_slot,
                    )
                )
                break

    return matched


def _match_trade_alerts(
    trades: list[TradeAlert],
    roster_names: set[str],
) -> list[UserTradeAlert]:
    matched: list[UserTradeAlert] = []

    for trade in trades:
        for roster_name in roster_names:
            if _names_match(roster_name, trade.player_name):
                fantasy_impact = _generate_trade_impact(trade)
                matched.append(
                    UserTradeAlert(
                        player_name=trade.player_name,
                        from_team=trade.from_team,
                        to_team=trade.to_team,
                        trade_date=trade.trade_date,
                        fantasy_impact=fantasy_impact,
                    )
                )
                break

    return matched


def _match_matchup_alerts(
    matchups: list[MatchupAlert],
    roster_names: set[str],
    lineup_analysis: LineupAnalysis | None = None,
) -> list[UserMatchupAlert]:
    matched: list[UserMatchupAlert] = []

    has_any_conflicts = bool(lineup_analysis and lineup_analysis.position_conflicts)

    for matchup in matchups:
        for roster_name in roster_names:
            if _names_match(roster_name, matchup.player_name):
                if lineup_analysis and not has_any_conflicts:
                    break

                fantasy_impact = _generate_matchup_impact(matchup)
                matched.append(
                    UserMatchupAlert(
                        player_name=matchup.player_name,
                        opponent=matchup.opponent,
                        opponent_goals_against_avg=matchup.opponent_goals_against_avg,
                        fantasy_impact=fantasy_impact,
                    )
                )
                break

    return matched


def _generate_injury_impact(
    injury: InjuryAlert,
    has_game_today: bool,
    is_new: bool,
    already_on_ir_slot: bool,
) -> str:
    if already_on_ir_slot:
        return f"Currently on IR slot. Status: {injury.status}. No roster action needed."

    if injury.status == "IR":
        return "Extended absence likely. Consider moving to IR slot and picking up a replacement."

    if has_game_today:
        if injury.status == "OUT":
            return "Expected to miss tonight's game. Consider benching or finding a replacement."
        if injury.status == "DTD":
            return "Game-time decision tonight. Monitor closely and have a backup ready."

    if is_new:
        if injury.status == "OUT":
            return "New injury — expected to miss upcoming games. Monitor for timeline updates."
        if injury.status == "DTD":
            return "New injury — day-to-day. Monitor for updates before their next game."

    return "Status unclear. Monitor for updates."


def _generate_trade_impact(trade: TradeAlert) -> str:
    return (
        f"Moved from {trade.from_team} to {trade.to_team}. "
        "Monitor for role changes and line assignments with new team."
    )


def _generate_matchup_impact(matchup: MatchupAlert) -> str:
    return (
        f"Favorable matchup against {matchup.opponent} "
        f"({matchup.opponent_goals_against_avg:.2f} GAA). "
        "Consider starting if available."
    )
