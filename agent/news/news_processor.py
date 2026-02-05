"""News processor for matching alerts against user rosters.

This module takes raw news alerts and a user's roster, then produces
personalized alerts enriched with fantasy impact context.
"""

from __future__ import annotations

from typing import Any

from agent.news.news_digest import (
    InjuryAlert,
    MatchupAlert,
    NewsDigest,
    RawNewsCollection,
    TradeAlert,
    UserInjuryAlert,
    UserMatchupAlert,
    UserTradeAlert,
)
from module.logger import get_logger

logger = get_logger(__name__)


def process_news_for_user(
    raw_news: RawNewsCollection,
    roster: list[Any],
    user_email: str,
    league_id: str,
    team_id: str,
    league_name: str,
    team_name: str,
) -> NewsDigest:
    """Process raw news collection against a user's roster.

    Args:
        raw_news: Collection of all raw alerts from data sources
        roster: User's fantasy roster (from Yahoo API)
        user_email: User's email address
        league_id: Yahoo league ID
        team_id: Yahoo team ID
        league_name: Name of the fantasy league
        team_name: Name of the user's team

    Returns:
        NewsDigest containing only alerts relevant to this user's roster
    """
    roster_players = _extract_roster_player_names(roster)

    logger.debug(f"Processing news for {user_email} with {len(roster_players)} rostered players")

    injury_alerts = _match_injury_alerts(raw_news.injuries, roster_players)
    trade_alerts = _match_trade_alerts(raw_news.trades, roster_players)
    matchup_alerts = _match_matchup_alerts(raw_news.matchups, roster_players)

    digest = NewsDigest(
        user_email=user_email,
        league_id=league_id,
        team_id=team_id,
        league_name=league_name,
        team_name=team_name,
        injury_alerts=injury_alerts,
        trade_alerts=trade_alerts,
        matchup_alerts=matchup_alerts,
    )

    logger.info(
        f"Generated digest for {user_email}: "
        f"{len(injury_alerts)} injuries, {len(trade_alerts)} trades, "
        f"{len(matchup_alerts)} matchups"
    )

    return digest


def _extract_roster_player_names(roster: list[Any]) -> set[str]:
    """Extract player names from Yahoo roster response.

    Args:
        roster: List of player objects from Yahoo API

    Returns:
        Set of lowercase player names for matching
    """
    names: set[str] = set()

    players = roster if isinstance(roster, list) else [roster] if roster else []

    for player in players:
        # Try different ways to get player name from Yahoo API response
        name_obj = getattr(player, "name", None)
        if name_obj:
            if hasattr(name_obj, "full"):
                names.add(str(name_obj.full).lower())
            elif hasattr(name_obj, "first") and hasattr(name_obj, "last"):
                full_name = f"{name_obj.first} {name_obj.last}"
                names.add(full_name.lower())
            else:
                names.add(str(name_obj).lower())

    return names


def _normalize_name(name: str) -> str:
    """Normalize player name for comparison.

    Args:
        name: Player name to normalize

    Returns:
        Lowercase, stripped name
    """
    return name.lower().strip()


def _names_match(roster_name: str, alert_name: str) -> bool:
    """Check if a roster player name matches an alert player name.

    Uses fuzzy matching to handle variations in name formatting,
    but requires first name/initial to match to avoid false positives
    (e.g., "Cale Makar" should not match "Taylor Makar").

    Args:
        roster_name: Name from user's roster (lowercase)
        alert_name: Name from alert (will be normalized)

    Returns:
        True if names match
    """
    alert_normalized = _normalize_name(alert_name)

    # Exact match
    if roster_name == alert_normalized:
        return True

    # Clean up names for comparison (remove periods, normalize spaces)
    roster_clean = roster_name.replace(".", "").replace("-", " ")
    alert_clean = alert_normalized.replace(".", "").replace("-", " ")

    # Exact match after cleaning
    if roster_clean == alert_clean:
        return True

    roster_parts = roster_clean.split()
    alert_parts = alert_clean.split()

    # If alert is just a last name, check if it matches roster's last name
    # This is acceptable since there's no first name to compare
    if len(alert_parts) == 1 and len(roster_parts) >= 2 and roster_parts[-1] == alert_parts[0]:
        return True

    # For full names, require BOTH last name AND first initial to match
    # This prevents "Cale Makar" from matching "Taylor Makar"
    if len(roster_parts) >= 2 and len(alert_parts) >= 2:
        last_names_match = roster_parts[-1] == alert_parts[-1]
        first_initial_match = roster_parts[0][0] == alert_parts[0][0]
        return last_names_match and first_initial_match

    return False


def _match_injury_alerts(
    injuries: list[InjuryAlert],
    roster_players: set[str],
) -> list[UserInjuryAlert]:
    """Match injury alerts against roster.

    Args:
        injuries: Raw injury alerts
        roster_players: Set of lowercase roster player names

    Returns:
        List of user-enriched injury alerts
    """
    matched: list[UserInjuryAlert] = []

    for injury in injuries:
        for roster_name in roster_players:
            if _names_match(roster_name, injury.player_name):
                fantasy_impact = _generate_injury_impact(injury)
                matched.append(
                    UserInjuryAlert(
                        player_name=injury.player_name,
                        team=injury.team,
                        status=injury.status,
                        description=injury.description,
                        fantasy_impact=fantasy_impact,
                    )
                )
                break

    return matched


def _match_trade_alerts(
    trades: list[TradeAlert],
    roster_players: set[str],
) -> list[UserTradeAlert]:
    """Match trade alerts against roster.

    Args:
        trades: Raw trade alerts
        roster_players: Set of lowercase roster player names

    Returns:
        List of user-enriched trade alerts
    """
    matched: list[UserTradeAlert] = []

    for trade in trades:
        for roster_name in roster_players:
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
    roster_players: set[str],
) -> list[UserMatchupAlert]:
    """Match matchup alerts against roster.

    Args:
        matchups: Raw matchup alerts
        roster_players: Set of lowercase roster player names

    Returns:
        List of user-enriched matchup alerts
    """
    matched: list[UserMatchupAlert] = []

    for matchup in matchups:
        for roster_name in roster_players:
            if _names_match(roster_name, matchup.player_name):
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


def _generate_injury_impact(injury: InjuryAlert) -> str:
    """Generate fantasy impact text for an injury alert.

    Args:
        injury: The injury alert

    Returns:
        Human-readable fantasy impact string
    """
    status_impacts = {
        "OUT": "Expected to miss tonight's game. Consider benching or finding a replacement.",
        "DTD": "Game-time decision. Monitor closely and have a backup ready.",
        "IR": "Extended absence likely. Consider picking up a replacement from waivers.",
    }
    return status_impacts.get(injury.status, "Status unclear. Monitor for updates.")


def _generate_trade_impact(trade: TradeAlert) -> str:
    """Generate fantasy impact text for a trade alert.

    Args:
        trade: The trade alert

    Returns:
        Human-readable fantasy impact string
    """
    return (
        f"Moved from {trade.from_team} to {trade.to_team}. "
        "Monitor for role changes and line assignments with new team."
    )


def _generate_matchup_impact(matchup: MatchupAlert) -> str:
    """Generate fantasy impact text for a matchup alert.

    Args:
        matchup: The matchup alert

    Returns:
        Human-readable fantasy impact string
    """
    return (
        f"Favorable matchup against {matchup.opponent} "
        f"({matchup.opponent_goals_against_avg:.2f} GAA). "
        "Consider starting if available."
    )
