"""Tool to get comprehensive player stats combining NHL API IDs, MoneyPuck stats, and Yahoo rank."""

import json
from typing import Any, TypedDict, cast

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.player_comparison.fuzzy_resolve_nhl_api_player_ids import (
    fuzzy_resolve_nhl_api_player_ids,
)
from tools.player_comparison.get_moneypuck_stats import get_moneypuck_stats
from tools.player_comparison.get_player_line_info import get_player_line_info
from tools.player_comparison.get_team_schedule import get_team_schedule
from tools.yahoo.get_player_season_rank import get_player_season_rank

logger = get_logger(__name__)


def calculate_undervalued_score(stats: dict[str, Any]) -> tuple[float, list[str]]:
    """Calculate how undervalued a player is based on underlying stats vs production.

    Higher score = more undervalued (better trade target).

    Factors:
    - Negative goals_above_expected (shooting below expected, due for regression up)
    - Strong Fenwick%/Corsi% (good possession, sustainable production)
    - High TOI (more opportunity)
    - Top line deployment (quality minutes)
    - Rank vs production disparity

    Returns:
        Tuple of (score, list of reasons explaining the score)
    """
    score = 0.0
    reasons: list[str] = []

    # 1. Goals Above Expected - negative means due for positive regression
    gae = stats.get("goals_above_expected", 0)
    x_goals = stats.get("x_goals", 0)
    goals = stats.get("goals", 0)

    if gae < -3 and x_goals > 5:
        score += 4
        reasons.append(
            f"Significant positive regression candidate: {goals}G vs {x_goals:.1f} xG (GAE: {gae:.1f})"
        )
    elif gae < -1.5 and x_goals > 3:
        score += 2
        reasons.append(
            f"Positive regression candidate: {goals}G vs {x_goals:.1f} xG (GAE: {gae:.1f})"
        )
    elif gae < 0:
        score += 0.5
        reasons.append(f"Slight positive regression possible: {goals}G vs {x_goals:.1f} xG")
    elif gae > 3:
        score -= 2
        reasons.append(
            f"WARNING: Overperforming, likely to regress DOWN: {goals}G vs {x_goals:.1f} xG (GAE: +{gae:.1f})"
        )

    # 2. Fenwick% - possession metric (50% is neutral)
    fenwick = stats.get("fenwick_pct", 50)
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

    # 3. Corsi% as secondary confirmation
    corsi = stats.get("corsi_pct", 50)
    if corsi > 54:
        score += 1
        reasons.append(f"Strong shot attempt share: {corsi:.1f}% Corsi")
    elif corsi < 46:
        score -= 1
        reasons.append(f"Weak shot attempt share: {corsi:.1f}% Corsi")

    # 4. Time on Ice - more ice time = more opportunity
    toi = stats.get("toi_per_game_minutes", 0)
    position = stats.get("position", "")

    # Adjust TOI expectations by position (D get more ice time)
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
    else:  # Forwards
        if toi > 19:
            score += 2
            reasons.append(f"Top-line ice time: {toi:.1f} min/game")
        elif toi > 17:
            score += 1
            reasons.append(f"Strong ice time: {toi:.1f} min/game")
        elif toi < 13:
            score -= 1
            reasons.append(f"Limited ice time: {toi:.1f} min/game")

    # 5. Line deployment - top lines get better opportunities
    line = stats.get("estimated_line_number")
    if line == 1:
        score += 2
        reasons.append("First line deployment")
    elif line == 2:
        score += 1
        reasons.append("Second line deployment")
    elif line and line >= 4:
        score -= 1
        reasons.append(f"Fourth line deployment (line {line})")

    # 6. Rank vs Points Per Game disparity
    # Lower rank number = better, higher PPG = better
    # If rank is much worse than PPG suggests, player is undervalued
    rank = stats.get("yahoo_rank")
    ppg = stats.get("points_per_game", 0)
    games = stats.get("games_played", 0)

    if rank and ppg > 0 and games >= 10:
        # Rough expected rank based on PPG (elite ~0.9+, good ~0.6-0.8, average ~0.4-0.5)
        # Rank 1-50 for elite, 50-150 for good, 150+ for average
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

        rank_disparity = rank - expected_rank

        if rank_disparity > 50:
            score += 2
            reasons.append(
                f"Significantly underranked: rank {rank} but {ppg:.2f} PPG suggests ~{expected_rank}"
            )
        elif rank_disparity > 25:
            score += 1
            reasons.append(f"Underranked: rank {rank} but {ppg:.2f} PPG suggests ~{expected_rank}")
        elif rank_disparity < -40:
            score -= 1
            reasons.append(f"Overranked: rank {rank} but {ppg:.2f} PPG suggests ~{expected_rank}")

    # 7. Schedule boost - more games = more counting stats opportunity
    games_this_week = stats.get("games_remaining_this_week")
    games_next_week = stats.get("games_next_week")

    if games_this_week is not None and games_next_week is not None:
        total_upcoming = games_this_week + games_next_week
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


class GetComprehensivePlayerStatsInput(BaseModel):
    """Input schema for get_comprehensive_player_stats tool."""

    player_names: list[str] = Field(
        description="List of player names to get stats for (e.g., ['Connor McDavid', 'Leon Draisaitl'])"
    )
    user_email: str = Field(description="User's email address for Yahoo authentication")
    league_id: str = Field(description="Yahoo fantasy league ID")
    situation: str = Field(
        default="all",
        description=(
            "Game situation for MoneyPuck stats: 'all' (default), '5on5', '5on4' (power play), "
            "'4on5' (penalty kill), 'other'"
        ),
    )


class LinemateDict(TypedDict, total=False):
    """Type definition for linemate info."""

    player_id: int
    name: str
    position: str
    shared_ice_time_seconds: int
    shared_ice_time_pct: float


class PlayerStatsDict(TypedDict, total=False):
    """Type definition for comprehensive player stats."""

    status: str
    name: str
    nhl_api_id: int
    team: str
    position: str
    # Yahoo fantasy data
    yahoo_rank: int | None
    yahoo_player_key: str | None
    ownership_type: str | None
    owner_team_name: str | None
    percent_owned: str | None
    injury_status: str | None
    # MoneyPuck stats
    games_played: int
    toi_per_game_minutes: float
    goals: int
    assists: int
    points: int
    points_per_game: float
    x_goals: float
    goals_above_expected: float
    fenwick_pct: float
    corsi_pct: float
    on_ice_xgoals_pct: float
    shots_on_goal: int
    high_danger_shots: int
    high_danger_goals: int
    hits: int
    takeaways: int
    giveaways: int
    # Schedule info
    games_remaining_this_week: int | None
    games_next_week: int | None
    # Line info
    estimated_line_number: int | None
    primary_linemates: list[LinemateDict]
    # Undervalued analysis
    undervalued_score: float | None
    undervalued_reasons: list[str]
    # Error tracking
    error: str | None
    warnings: list[str]


def _get_comprehensive_player_stats_impl(
    player_names: list[str],
    user_email: str,
    league_id: str,
    situation: str = "all",
) -> str:
    """Internal implementation for get_comprehensive_player_stats."""
    results: dict[str, PlayerStatsDict] = {}

    try:
        # Step 1: Resolve player names to NHL API IDs
        logger.info(f"Resolving NHL API IDs for {len(player_names)} players")
        resolve_response = fuzzy_resolve_nhl_api_player_ids(player_names)
        resolve_data = json.loads(resolve_response)

        player_id_map: dict[str, tuple[int, str]] = {}  # player_name -> (nhl_id, full_name)

        for player_name in player_names:
            player_result: PlayerStatsDict = {
                "status": "error",
                "name": player_name,
                "warnings": [],
            }

            resolve_info = resolve_data.get(player_name, {})
            resolve_status = resolve_info.get("status")

            if resolve_status == "success":
                nhl_id = resolve_info.get("player_id")
                full_name = resolve_info.get("full_name", player_name)
                player_id_map[player_name] = (nhl_id, full_name)
                player_result["nhl_api_id"] = nhl_id
                player_result["name"] = full_name
                player_result["status"] = "partial"  # Will update if we get more data
            elif resolve_status == "multiple_matches":
                matches = resolve_info.get("matches", [])
                player_result["error"] = (
                    f"Multiple matches found: {', '.join(m.get('full_name', '?') for m in matches[:3])}"
                )
                results[player_name] = player_result
                continue
            else:
                error_msg = resolve_info.get("message", "Player not found")
                player_result["error"] = error_msg
                results[player_name] = player_result
                continue

        # Step 2: Fetch MoneyPuck stats for all resolved players
        if player_id_map:
            nhl_ids = [pid for pid, _ in player_id_map.values()]
            logger.info(f"Fetching MoneyPuck stats for {len(nhl_ids)} players")

            try:
                moneypuck_response = get_moneypuck_stats(player_ids=nhl_ids, situation=situation)
                moneypuck_data = json.loads(moneypuck_response)
            except Exception as e:
                logger.error(f"MoneyPuck fetch failed: {e}")
                raise  # Re-raise to make this a hard error instead of silently continuing

            # Step 3: Fetch team schedules for all unique teams
            teams_to_fetch = set()
            team_map: dict[int, str] = {}  # player_id -> team_abbrev

            # First pass - extract teams from MoneyPuck data
            for _player_name, (nhl_id, _full_name) in player_id_map.items():
                mp_stats = moneypuck_data.get(str(nhl_id), {})
                if mp_stats.get("status") == "success":
                    team = mp_stats.get("stats", {}).get("team")
                    if team:
                        teams_to_fetch.add(team)
                        team_map[nhl_id] = team

            # Fetch schedules for all teams in one call
            schedule_data: dict[str, Any] = {}
            if teams_to_fetch:
                try:
                    schedule_response = get_team_schedule(list(teams_to_fetch))
                    schedule_data = json.loads(schedule_response)
                except Exception as e:
                    logger.error(f"Team schedule fetch failed: {e}")

            # Step 4: Fetch line info for all players
            linemate_data: dict[str, Any] = {}
            if player_id_map:
                try:
                    nhl_ids = [pid for pid, _ in player_id_map.values()]
                    linemate_response = get_player_line_info(nhl_ids)
                    linemate_data = json.loads(linemate_response)
                except Exception as e:
                    logger.error(f"Line info fetch failed: {e}")

            # Step 5: Combine all data for each player
            for player_name, (nhl_id, full_name) in player_id_map.items():
                player_result: PlayerStatsDict = {
                    "status": "success",
                    "name": full_name,
                    "nhl_api_id": nhl_id,
                    "warnings": [],
                }

                # Add MoneyPuck stats
                mp_stats = moneypuck_data.get(str(nhl_id), {})
                if mp_stats.get("status") == "success":
                    stats = mp_stats.get("stats", {})
                    player_result.update(
                        {
                            "team": stats.get("team"),
                            "position": stats.get("position"),
                            "games_played": stats.get("games_played", 0),
                            "toi_per_game_minutes": stats.get("toi_per_game_minutes", 0.0),
                            "goals": stats.get("goals", 0),
                            "assists": stats.get("primary_assists", 0)
                            + stats.get("secondary_assists", 0),
                            "points": stats.get("points", 0),
                            "points_per_game": stats.get("points_per_game", 0.0),
                            "x_goals": stats.get("x_goals", 0.0),
                            "goals_above_expected": stats.get("goals_above_expected", 0.0),
                            "fenwick_pct": stats.get("fenwick_pct", 0.0),
                            "corsi_pct": stats.get("corsi_pct", 0.0),
                            "on_ice_xgoals_pct": stats.get("on_ice_xgoals_pct", 0.0),
                            "shots_on_goal": stats.get("shots_on_goal", 0),
                            "high_danger_shots": stats.get("high_danger_shots", 0),
                            "high_danger_goals": stats.get("high_danger_goals", 0),
                            "hits": stats.get("hits", 0),
                            "takeaways": stats.get("takeaways", 0),
                            "giveaways": stats.get("giveaways", 0),
                        }
                    )
                else:
                    warning = (
                        f"MoneyPuck data not available: {mp_stats.get('message', 'unknown error')}"
                    )
                    player_result["warnings"].append(warning)
                    logger.warning(f"{full_name}: {warning}")

                # Add Yahoo fantasy rank
                try:
                    yahoo_response = get_player_season_rank(
                        user_email=user_email,
                        league_id=league_id,
                        player_name=full_name,
                    )
                    yahoo_data = json.loads(yahoo_response)

                    if yahoo_data.get("player"):
                        yahoo_player = yahoo_data["player"]
                        player_result.update(
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
                        player_result["warnings"].append(warning)
                        logger.warning(f"{full_name}: {warning}")
                except Exception as e:
                    warning = f"Yahoo rank lookup failed: {e!s}"
                    player_result["warnings"].append(warning)
                    logger.error(f"{full_name}: {warning}")

                # Add schedule info
                player_team = team_map.get(nhl_id)
                if player_team and player_team in schedule_data:
                    team_schedule = schedule_data[player_team]
                    if team_schedule.get("status") == "success":
                        player_result.update(
                            {
                                "games_remaining_this_week": team_schedule.get("this_week_games"),
                                "games_next_week": team_schedule.get("next_week_games"),
                            }
                        )
                    else:
                        warning = (
                            f"Schedule not available: {team_schedule.get('message', 'unknown')}"
                        )
                        player_result["warnings"].append(warning)
                        logger.warning(f"{full_name}: {warning}")

                # Add linemate info
                line_info = linemate_data.get(str(nhl_id), {})
                if line_info.get("status") == "success":
                    player_result.update(
                        {
                            "estimated_line_number": line_info.get("estimated_line_number"),
                            "primary_linemates": line_info.get("primary_linemates", []),
                        }
                    )
                elif line_info.get("status") == "error":
                    warning = f"Line info not available: {line_info.get('message', 'unknown')}"
                    player_result["warnings"].append(warning)
                    logger.warning(f"{full_name}: {warning}")

                # Calculate undervalued score based on all collected stats
                undervalued_score, undervalued_reasons = calculate_undervalued_score(
                    cast(dict[str, Any], cast(object, player_result))
                )
                player_result["undervalued_score"] = undervalued_score
                player_result["undervalued_reasons"] = undervalued_reasons

                # Clean up warnings if empty
                if not player_result.get("warnings"):
                    player_result.pop("warnings", None)

                results[player_name] = player_result

        return json.dumps(results, indent=2)

    except Exception as e:
        logger.error(f"Error in get_comprehensive_player_stats: {e}")
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "message": "Failed to fetch comprehensive player stats",
            }
        )


# Expose for internal use by other Python code
get_comprehensive_player_stats_internal = _get_comprehensive_player_stats_impl


@tool(args_schema=GetComprehensivePlayerStatsInput)
def get_comprehensive_player_stats(
    player_names: list[str],
    user_email: str,
    league_id: str,
    situation: str = "all",
) -> str:
    """
    Get comprehensive stats for multiple players including NHL IDs, MoneyPuck advanced stats, Yahoo fantasy rank, schedule, and linemates.

    Automatically uses the current NHL season.

    This is a consolidated tool that:
    1. Resolves player names to NHL API IDs using fuzzy matching
    2. Fetches advanced stats from MoneyPuck (xGoals, Fenwick%, Corsi%, etc.) for current season
    3. Gets Yahoo fantasy league rank and ownership info
    4. Gets games remaining this week and next week for each player's team
    5. Gets linemate information including player IDs for easy lookup
    6. Calculates an undervalued_score to identify regression candidates

    Args:
        player_names: List of player names to search for (partial names work)
        user_email: User's email for Yahoo OAuth
        league_id: Yahoo fantasy league ID
        situation: MoneyPuck game situation filter (all, 5on5, 5on4, 4on5, other)

    Returns:
        JSON string with comprehensive stats for each player
    """
    return _get_comprehensive_player_stats_impl(player_names, user_email, league_id, situation)
