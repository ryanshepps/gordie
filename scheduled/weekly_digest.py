from __future__ import annotations

import json

from client.moneypuck_cli import get_player_stats_by_names
from data.pydantic_models import (
    DigestData,
    EnrichedFreeAgent,
    PlayerPerformance,
    RosterPerformance,
    ScheduleTip,
)
from module.logger import get_logger
from tools.available.search_available_players import search_available_players
from tools.hockey.player.get_team_schedule import get_team_schedule

logger = get_logger(__name__)


def _get_player_name(player: object) -> str:
    """Extract player name from player object."""
    name_obj = getattr(player, "name", None)
    if name_obj and hasattr(name_obj, "full"):
        return name_obj.full
    return str(name_obj) if name_obj else "Unknown"


def _fetch_and_enrich_free_agents(user_email: str, league_id: str) -> list[EnrichedFreeAgent]:
    """Fetch hot free agents and enrich with advanced stats."""
    try:
        fa_json = search_available_players.invoke(
            {
                "user_email": user_email,
                "league_id": league_id,
                "status": "FA",
                "sort": "AR",
                "sort_type": "lastweek",
                "count": 5,
            }
        )
        fa_data = json.loads(fa_json)
        players = fa_data.get("players", [])

        if not players:
            return []

        player_names = [p["name"] for p in players]
        stats_data = get_player_stats_by_names(player_names)

        nhl_teams = {p["name"]: p.get("team", "") for p in players}
        unique_teams = list({t for t in nhl_teams.values() if t})
        schedule_data: dict[str, dict[str, object]] = {}
        if unique_teams:
            try:
                schedule_json = get_team_schedule(unique_teams)
                schedule_data = json.loads(schedule_json)
            except Exception as e:
                logger.warning(f"Failed to fetch schedule for free agents: {e}")

        result: list[EnrichedFreeAgent] = []
        for player in players:
            name = player.get("name", "Unknown")
            team = player.get("team", "")
            enriched = EnrichedFreeAgent(
                name=name,
                position=player.get("position"),
                team=team,
                percent_owned=player.get("percent_owned"),
            )

            if name in stats_data:
                stats = stats_data[name]
                goals = int(stats.get("goals", stats.get("I_F_goals", 0)) or 0)
                points = int(stats.get("points", stats.get("I_F_points", 0)) or 0)
                assists = points - goals
                corsi = stats.get("corsi_pct", stats.get("onIce_corsiPercentage"))
                corsi_pct = float(corsi) if corsi else None

                games_this_week: int | None = None
                team_upper = team.upper() if team else ""
                if team_upper in schedule_data:
                    team_sched = schedule_data[team_upper]
                    if team_sched.get("status") == "success":
                        raw_games = team_sched.get("this_week_games", 0) or 0
                        games_this_week = int(str(raw_games))

                enriched = EnrichedFreeAgent(
                    name=name,
                    position=player.get("position"),
                    team=team,
                    percent_owned=player.get("percent_owned"),
                    goals=goals,
                    assists=max(0, assists),
                    corsi_pct=corsi_pct,
                    games_this_week=games_this_week,
                )

            result.append(enriched)

        return result

    except Exception as e:
        logger.warning(f"Failed to fetch hot free agents: {e}")
        return []


def _categorize_roster_by_performance(
    last_week_roster: list[object] | object,
    current_roster: list[object] | object,
) -> RosterPerformance:
    """Categorize players into top performers, underperformers, and injured."""
    # Build injury status lookup from current roster
    injury_status: dict[str, str] = {}
    current_players = (
        current_roster
        if isinstance(current_roster, list)
        else [current_roster]
        if current_roster
        else []
    )
    for player in current_players:
        name = _get_player_name(player)
        status = getattr(player, "status", None)
        if status and status.upper() in ("IR", "IR+", "O", "DTD"):
            injury_status[name] = getattr(player, "status_full", status)

    # Score and sort players by last week points
    scored_players: list[PlayerPerformance] = []
    last_week_players = (
        last_week_roster
        if isinstance(last_week_roster, list)
        else [last_week_roster]
        if last_week_roster
        else []
    )
    for player in last_week_players:
        name = _get_player_name(player)
        position = getattr(player, "display_position", "")
        nhl_team = getattr(player, "editorial_team_abbr", "")

        player_points = getattr(player, "player_points", None)
        points = float(getattr(player_points, "total", 0)) if player_points else 0.0

        scored_players.append(
            PlayerPerformance(
                name=name,
                position=position,
                team=nhl_team,
                points=points,
                injury=injury_status.get(name),
            )
        )

    # Separate injured from active
    injured = [p for p in scored_players if p.injury]
    active = [p for p in scored_players if not p.injury]

    # Sort active by points descending
    active.sort(key=lambda x: x.points, reverse=True)

    return RosterPerformance(
        top_performers=active[:5],
        underperformers=active[-3:] if len(active) > 5 else [],
        injured=injured,
    )


def _extract_nhl_teams(roster: list[object] | object) -> list[str]:
    """Extract unique NHL team abbreviations from roster."""
    teams: set[str] = set()
    players = roster if isinstance(roster, list) else [roster] if roster else []
    for player in players:
        team = getattr(player, "editorial_team_abbr", None)
        if team:
            teams.add(team.upper())
    return list(teams)


def _build_schedule_tips(roster: list[object] | object) -> list[ScheduleTip]:
    """Build schedule-based tips."""
    nhl_teams = _extract_nhl_teams(roster)
    if not nhl_teams:
        return []

    try:
        schedule_json = get_team_schedule(nhl_teams)
        schedule_data = json.loads(schedule_json)
    except Exception as e:
        logger.warning(f"Failed to fetch schedule: {e}")
        return []

    # Group players by NHL team
    team_players: dict[str, list[str]] = {}
    players = roster if isinstance(roster, list) else [roster] if roster else []
    for player in players:
        team = getattr(player, "editorial_team_abbr", "")
        if team:
            team = team.upper()
            name = _get_player_name(player)
            if team not in team_players:
                team_players[team] = []
            team_players[team].append(name)

    tips: list[ScheduleTip] = []

    for team, player_names in team_players.items():
        if team not in schedule_data:
            continue

        team_info = schedule_data[team]
        if team_info.get("status") != "success":
            continue

        games_this_week = team_info.get("this_week_games", 0)

        if games_this_week >= 4:
            tips.append(
                ScheduleTip(
                    team=team,
                    games_this_week=games_this_week,
                    player_names=player_names[:3],
                    tip_type="advantage",
                )
            )
        elif games_this_week <= 2:
            tips.append(
                ScheduleTip(
                    team=team,
                    games_this_week=games_this_week,
                    player_names=player_names[:3],
                    tip_type="warning",
                )
            )

    return tips[:6]  # Limit to 6 tips


def build_digest_content(data: DigestData) -> str:
    """Build digest content in markdown format.

    Args:
        data: DigestData containing all information for the digest

    Returns:
        Markdown-formatted content for the digest
    """
    sections: list[str] = []

    # Header
    sections.append(
        f"Hey there! Here's your Week {data.current_week} update for "
        f"{data.team_name} in {data.league_name}."
    )
    sections.append("")

    # Matchup Preview
    if data.current_matchup:
        sections.append("## This Week's Matchup")
        sections.append("")
        sections.append(f"**Opponent:** {data.current_matchup.opponent_name}")
        sections.append(f"**Their Record:** {data.current_matchup.opponent_record}")
        sections.append("")

    # Last Week's Performance
    sections.append("## Last Week's Performance")
    sections.append("")

    if data.roster_performance.top_performers:
        sections.append("**Top Performers:**")
        for p in data.roster_performance.top_performers:
            sections.append(f"- {p.name} ({p.position}) - **{p.points:.1f} pts**")
        sections.append("")

    if data.roster_performance.underperformers:
        sections.append("**Underperformers (consider benching/dropping):**")
        for p in data.roster_performance.underperformers:
            sections.append(f"- {p.name} ({p.position}) - {p.points:.1f} pts")
        sections.append("")

    if data.roster_performance.injured:
        sections.append("**Injured Players:**")
        for p in data.roster_performance.injured:
            sections.append(f"- {p.name} ({p.position}) - *{p.injury}*")
        sections.append("")

    # Recommendations
    sections.append("## Recommendations")
    sections.append("")

    if data.hot_free_agents:
        sections.append("**Hot Free Agents (last week):**")
        for fa in data.hot_free_agents:
            parts = [f"{fa.name} ({fa.position}, {fa.team})"]
            stats: list[str] = []
            if fa.goals > 0:
                stats.append(f"{fa.goals}G")
            if fa.assists > 0:
                stats.append(f"{fa.assists}A")
            if fa.corsi_pct:
                stats.append(f"{fa.corsi_pct:.1f}% Corsi")
            if fa.percent_owned:
                stats.append(f"{fa.percent_owned}% owned")
            if fa.games_this_week:
                stats.append(f"{fa.games_this_week} games this week")
            if stats:
                parts.append(" - ".join(stats))
            sections.append(f"- {', '.join(parts)}")
        sections.append("")

    if data.schedule_tips:
        sections.append("**Schedule Watch:**")
        for tip in data.schedule_tips:
            player_str = ", ".join(tip.player_names[:2])
            if tip.tip_type == "advantage":
                sections.append(
                    f"- {tip.team} has {tip.games_this_week} games this week ({player_str})"
                )
            else:
                sections.append(
                    f"- {tip.team} only has {tip.games_this_week} games - "
                    f"consider benching ({player_str})"
                )
        sections.append("")

    # Footer
    sections.append("Good luck this week!")
    sections.append("")
    sections.append("*- Gordie*")

    return "\n".join(sections)
