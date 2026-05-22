"""Tool to calculate undervalued player scores using pre-fetched stats and Yahoo/schedule data."""

import json
from collections.abc import Mapping
from typing import TypedDict

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.hockey.player.get_team_schedule import get_team_schedule
from tools.yahoo.get_player_season_rank import get_player_season_rank

logger = get_logger(__name__)


class MoneyPuckStats(BaseModel):
    """Pre-fetched MoneyPuck stats for a player."""

    player_name: str = Field(description="Player's full name")
    team: str = Field(description="Team abbreviation (e.g., 'TOR', 'EDM')")
    position: str = Field(description="Player position (C, LW, RW, D, L, R)")
    games_played: int = Field(description="Number of games played", ge=1)
    goals: int = Field(description="Goals scored", ge=0)
    points: int = Field(description="Total points", ge=0)
    points_per_game: float = Field(description="Points per game", ge=0)
    x_goals: float = Field(description="Expected goals from MoneyPuck", ge=0)
    fenwick_pct: float = Field(description="Fenwick percentage (typically 45-55)", gt=0, le=100)
    corsi_pct: float = Field(description="Corsi percentage (typically 45-55)", gt=0, le=100)
    toi_per_game_minutes: float = Field(description="Average TOI per game in minutes", gt=0)


class CalculateUndervaluedScoreInput(BaseModel):
    """Input schema for calculate_undervalued_score tool."""

    stats: MoneyPuckStats = Field(description="Pre-fetched MoneyPuck stats for the player")
    user_email: str = Field(description="User's email address for Yahoo authentication")
    league_id: str = Field(description="Yahoo fantasy league ID")


class LinemateDict(TypedDict, total=False):
    """Type definition for linemate info."""

    player_id: int
    name: str
    position: str
    shared_ice_time_seconds: int
    shared_ice_time_pct: float


class PlayerScoreDict(TypedDict, total=False):
    """Type definition for the undervalued score result."""

    status: str
    name: str
    team: str
    position: str
    games_played: int
    toi_per_game_minutes: float
    goals: int
    points: int
    points_per_game: float
    x_goals: float
    goals_above_expected: float
    fenwick_pct: float
    corsi_pct: float
    yahoo_rank: int | None
    yahoo_player_key: str | None
    ownership_type: str | None
    owner_team_name: str | None
    percent_owned: str | None
    injury_status: str | None
    games_remaining_this_week: int | None
    games_next_week: int | None
    estimated_line_number: int | None
    primary_linemates: list[LinemateDict]
    undervalued_score: float
    undervalued_reasons: list[str]
    warnings: list[str]


StatsValue = str | int | float | None


def _to_float(val: StatsValue, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_int(val: StatsValue, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _calculate_score(stats: "Mapping[str, StatsValue]") -> tuple[float, list[str]]:
    """Calculate how undervalued a player is based on underlying stats vs production.

    Higher score = more undervalued (better trade target).

    Factors:
    - Negative goals_above_expected (shooting below expected, due for regression up)
    - Strong Fenwick%/Corsi% (good possession, sustainable production)
    - High TOI (more opportunity)
    - Top line deployment (quality minutes)
    - Rank vs production disparity
    """
    score = 0.0
    reasons: list[str] = []

    gae = _to_float(stats.get("goals_above_expected"))
    x_goals = _to_float(stats.get("x_goals"))
    goals = _to_int(stats.get("goals"))
    games = _to_int(stats.get("games_played"))

    gae_per_82 = gae * (82 / games) if games >= 5 else 0.0

    if games >= 5 and gae_per_82 < -3 and x_goals > (5 * games / 82):
        score += 4
        reasons.append(
            f"Significant positive regression candidate: {goals}G vs {x_goals:.1f} xG in {games}GP (GAE/82: {gae_per_82:.1f})"
        )
    elif games >= 5 and gae_per_82 < -1.5 and x_goals > (3 * games / 82):
        score += 2
        reasons.append(
            f"Positive regression candidate: {goals}G vs {x_goals:.1f} xG in {games}GP (GAE/82: {gae_per_82:.1f})"
        )
    elif gae < 0:
        score += 0.5
        reasons.append(f"Slight positive regression possible: {goals}G vs {x_goals:.1f} xG")
    elif games >= 5 and gae_per_82 > 3:
        score -= 2
        reasons.append(
            f"WARNING: Overperforming, likely to regress DOWN: {goals}G vs {x_goals:.1f} xG in {games}GP (GAE/82: +{gae_per_82:.1f})"
        )

    fenwick = _to_float(stats.get("fenwick_pct"), 50.0)
    if fenwick > 55:
        score += 3
        reasons.append(f"Elite possession: {fenwick:.1f}% Fenwick")
    elif fenwick > 53:
        score += 2
        reasons.append(f"Strong possession: {fenwick:.1f}% Fenwick")
    elif fenwick > 51:
        score += 1
        reasons.append(f"Good possession: {fenwick:.1f}% Fenwick")
    elif fenwick < 47:
        score -= 2
        reasons.append(f"WARNING: Poor possession: {fenwick:.1f}% Fenwick")
    elif fenwick < 49:
        score -= 1
        reasons.append(f"Below average possession: {fenwick:.1f}% Fenwick")

    corsi = _to_float(stats.get("corsi_pct"), 50.0)
    if corsi > 54:
        score += 1
        reasons.append(f"Strong shot attempt share: {corsi:.1f}% Corsi")
    elif corsi < 46:
        score -= 1
        reasons.append(f"Weak shot attempt share: {corsi:.1f}% Corsi")

    toi = _to_float(stats.get("toi_per_game_minutes"))
    position = str(stats.get("position") or "")

    if position == "D":
        if toi > 22:
            score += 2
            reasons.append(f"Top-pairing ice time: {toi:.1f} min/game")
        elif toi > 20:
            score += 1
            reasons.append(f"Strong ice time for D: {toi:.1f} min/game")
        elif toi < 16:
            score -= 1
            reasons.append(f"Limited ice time: {toi:.1f} min/game")
    else:
        if toi > 19:
            score += 2
            reasons.append(f"Top-line ice time: {toi:.1f} min/game")
        elif toi > 17:
            score += 1
            reasons.append(f"Strong ice time: {toi:.1f} min/game")
        elif toi < 13:
            score -= 1
            reasons.append(f"Limited ice time: {toi:.1f} min/game")

    line = stats.get("estimated_line_number")
    if line == 1:
        score += 2
        reasons.append("First line deployment")
    elif line == 2:
        score += 1
        reasons.append("Second line deployment")
    elif line and int(line) >= 4:
        score -= 1
        reasons.append(f"Fourth line deployment (line {line})")

    rank = stats.get("yahoo_rank")
    ppg = float(stats.get("points_per_game", 0) or 0)
    games = int(stats.get("games_played", 0) or 0)

    if rank and ppg > 0 and games >= 10:
        rank_int = int(rank)
        if ppg >= 1.0:
            expected_rank = 30
        elif ppg >= 0.8:
            expected_rank = 60
        elif ppg >= 0.6:
            expected_rank = 100
        elif ppg >= 0.4:
            expected_rank = 150
        else:
            expected_rank = 200

        rank_disparity = rank_int - expected_rank

        if rank_disparity > 50:
            score += 2
            reasons.append(
                f"Significantly underranked: rank {rank_int} but {ppg:.2f} PPG suggests ~{expected_rank}"
            )
        elif rank_disparity > 25:
            score += 1
            reasons.append(
                f"Underranked: rank {rank_int} but {ppg:.2f} PPG suggests ~{expected_rank}"
            )
        elif rank_disparity < -40:
            score -= 1
            reasons.append(
                f"Overranked: rank {rank_int} but {ppg:.2f} PPG suggests ~{expected_rank}"
            )

    games_this_week = stats.get("games_remaining_this_week")
    games_next_week = stats.get("games_next_week")

    if games_this_week is not None and games_next_week is not None:
        total_upcoming = int(games_this_week) + int(games_next_week)
        if total_upcoming >= 7:
            score += 1
            reasons.append(
                f"Favorable schedule: {games_this_week} games this week, {games_next_week} next week"
            )
        elif total_upcoming <= 4:
            score -= 0.5
            reasons.append(
                f"Light schedule: {games_this_week} games this week, {games_next_week} next week"
            )

    return score, reasons


@tool(args_schema=CalculateUndervaluedScoreInput)
def calculate_undervalued_score(
    stats: MoneyPuckStats,
    user_email: str,
    league_id: str,
) -> str:
    """Calculate an undervalued score for a player using pre-fetched MoneyPuck stats.

    This tool takes stats you already fetched via query_stats_db and enriches them with:
    1. Yahoo fantasy league rank and ownership info
    2. Team schedule (games this week and next week)
    3. Linemate information
    4. An undervalued_score indicating trade/pickup value

    Score interpretation:
    - > 5: Highly undervalued — STRONG BUY
    - 3-5: Moderately undervalued — good target
    - 0-3: Fairly valued
    - < 0: OVERVALUED — avoid acquiring

    You MUST first use query_stats_db to get the player's stats, then pass them here.

    Args:
        stats: Pre-fetched MoneyPuck stats for the player
        user_email: User's email for Yahoo OAuth
        league_id: Yahoo fantasy league ID

    Returns:
        JSON string with comprehensive player data including undervalued score
    """
    player_name = stats.player_name
    team = stats.team
    goals_above_expected = stats.goals - stats.x_goals

    result: PlayerScoreDict = {
        "status": "success",
        "name": player_name,
        "team": team,
        "position": stats.position,
        "games_played": stats.games_played,
        "toi_per_game_minutes": stats.toi_per_game_minutes,
        "goals": stats.goals,
        "points": stats.points,
        "points_per_game": stats.points_per_game,
        "x_goals": stats.x_goals,
        "goals_above_expected": round(goals_above_expected, 2),
        "fenwick_pct": stats.fenwick_pct,
        "corsi_pct": stats.corsi_pct,
        "warnings": [],
    }

    try:
        yahoo_response = get_player_season_rank(
            user_email=user_email,
            league_id=league_id,
            player_name=player_name,
        )
        yahoo_data = json.loads(yahoo_response)

        if yahoo_data.get("player"):
            yahoo_player = yahoo_data["player"]
            result.update(
                {
                    "yahoo_rank": yahoo_player.get("rank"),
                    "yahoo_player_key": yahoo_player.get("player_key"),
                    "ownership_type": yahoo_player.get("ownership_type"),
                    "owner_team_name": yahoo_player.get("owner_team_name"),
                    "percent_owned": yahoo_player.get("percent_owned"),
                    "injury_status": yahoo_player.get("injury_status"),
                }
            )
        else:
            warning = f"Yahoo rank not found: {yahoo_data.get('error', 'unknown')}"
            result["warnings"].append(warning)
            logger.warning(f"{player_name}: {warning}")
    except Exception as e:
        warning = f"Yahoo rank lookup failed: {e!s}"
        result["warnings"].append(warning)
        logger.error(f"{player_name}: {warning}")

    try:
        schedule_response = get_team_schedule([team])
        schedule_data = json.loads(schedule_response)

        if team in schedule_data:
            team_schedule = schedule_data[team]
            if team_schedule.get("status") == "success":
                result.update(
                    {
                        "games_remaining_this_week": team_schedule.get("this_week_games"),
                        "games_next_week": team_schedule.get("next_week_games"),
                    }
                )
            else:
                warning = f"Schedule not available: {team_schedule.get('message', 'unknown')}"
                result["warnings"].append(warning)
                logger.warning(f"{player_name}: {warning}")
    except Exception as e:
        warning = f"Schedule fetch failed: {e!s}"
        result["warnings"].append(warning)
        logger.error(f"{player_name}: {warning}")

    score_input: dict[str, StatsValue] = {
        "goals_above_expected": result.get("goals_above_expected"),
        "x_goals": result.get("x_goals"),
        "goals": result.get("goals"),
        "fenwick_pct": result.get("fenwick_pct"),
        "corsi_pct": result.get("corsi_pct"),
        "toi_per_game_minutes": result.get("toi_per_game_minutes"),
        "position": result.get("position"),
        "estimated_line_number": result.get("estimated_line_number"),
        "yahoo_rank": result.get("yahoo_rank"),
        "points_per_game": result.get("points_per_game"),
        "games_played": result.get("games_played"),
        "games_remaining_this_week": result.get("games_remaining_this_week"),
        "games_next_week": result.get("games_next_week"),
    }
    undervalued_score, undervalued_reasons = _calculate_score(score_input)
    result["undervalued_score"] = undervalued_score
    result["undervalued_reasons"] = undervalued_reasons

    if not result.get("warnings"):
        result.pop("warnings", None)

    return json.dumps(result, indent=2)
