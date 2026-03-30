import json

from langchain.tools import tool
from pydantic import BaseModel, Field

from module.logger import get_logger
from tools.player_comparison.get_team_schedule import get_team_schedule
from tools.yahoo.get_player_season_rank import get_player_season_rank

logger = get_logger(__name__)


class BatterStats(BaseModel):
    player_name: str = Field(description="Player's full name")
    team: str = Field(description="Team abbreviation (e.g., 'NYY', 'LAD')")
    position: str = Field(description="Player position (1B, 2B, SS, 3B, OF, C, DH)")
    games_played: int = Field(description="Games played", ge=1)
    batting_avg: float = Field(description="Batting average", ge=0, le=0.500)
    obp: float = Field(description="On-base percentage", ge=0, le=0.700)
    slg: float = Field(description="Slugging percentage", ge=0, le=1.000)
    ops: float = Field(description="OPS (OBP + SLG)", ge=0, le=1.700)
    woba: float = Field(description="Weighted on-base average", ge=0, le=0.600)
    xwoba: float = Field(description="Expected wOBA from Statcast", ge=0, le=0.600)
    barrel_pct: float = Field(description="Barrel percentage", ge=0, le=30)
    hard_hit_pct: float = Field(description="Hard hit percentage", ge=0, le=70)
    k_pct: float = Field(description="Strikeout percentage", ge=0, le=50)
    bb_pct: float = Field(description="Walk percentage", ge=0, le=30)
    sprint_speed: float | None = Field(default=None, description="Sprint speed in ft/s", ge=20, le=35)
    hr: int = Field(description="Home runs", ge=0)
    rbi: int = Field(description="Runs batted in", ge=0)
    sb: int = Field(description="Stolen bases", ge=0)
    runs: int = Field(description="Runs scored", ge=0)


class PitcherStats(BaseModel):
    player_name: str = Field(description="Player's full name")
    team: str = Field(description="Team abbreviation (e.g., 'NYY', 'LAD')")
    position: str = Field(description="Pitcher role: 'SP' or 'RP'")
    games_played: int = Field(description="Games played", ge=1)
    era: float = Field(description="Earned run average", ge=0, le=15)
    xera: float = Field(description="Expected ERA from Statcast", ge=0, le=15)
    fip: float = Field(description="Fielding independent pitching", ge=0, le=15)
    xfip: float = Field(description="Expected FIP", ge=0, le=15)
    whip: float = Field(description="Walks + hits per inning pitched", ge=0, le=3)
    k_pct: float = Field(description="Strikeout percentage", ge=0, le=50)
    bb_pct: float = Field(description="Walk percentage", ge=0, le=25)
    barrel_pct_against: float = Field(description="Barrel percentage allowed", ge=0, le=30)
    hard_hit_pct_against: float = Field(description="Hard hit percentage allowed", ge=0, le=60)
    innings_pitched: float = Field(description="Innings pitched", ge=0)
    wins: int = Field(description="Wins", ge=0)
    saves: int = Field(description="Saves", ge=0)


class CalculateMLBUndervaluedInput(BaseModel):
    batter_stats: BatterStats | None = Field(default=None, description="Pre-fetched batter stats")
    pitcher_stats: PitcherStats | None = Field(default=None, description="Pre-fetched pitcher stats")
    user_email: str = Field(description="User's email address for Yahoo authentication")
    league_id: str = Field(description="Yahoo fantasy league ID")


def _calculate_batter_score(stats: BatterStats) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    woba_gap = stats.xwoba - stats.woba

    if woba_gap > 0.030:
        score += 4
        reasons.append(
            f"Significant luck regression candidate: {stats.woba:.3f} wOBA vs {stats.xwoba:.3f} xwOBA (gap: +{woba_gap:.3f})"
        )
    elif woba_gap > 0.015:
        score += 2
        reasons.append(
            f"Moderate regression candidate: {stats.woba:.3f} wOBA vs {stats.xwoba:.3f} xwOBA (gap: +{woba_gap:.3f})"
        )
    elif woba_gap < -0.030:
        score -= 2
        reasons.append(
            f"WARNING: Overperforming, will regress down: {stats.woba:.3f} wOBA vs {stats.xwoba:.3f} xwOBA (gap: {woba_gap:.3f})"
        )

    if stats.barrel_pct > 12:
        score += 3
        reasons.append(f"Elite contact quality: {stats.barrel_pct:.1f}% Barrel")
    elif stats.barrel_pct > 8:
        score += 2
        reasons.append(f"Strong contact quality: {stats.barrel_pct:.1f}% Barrel")
    elif stats.barrel_pct > 5:
        score += 1
        reasons.append(f"Above average contact quality: {stats.barrel_pct:.1f}% Barrel")
    elif stats.barrel_pct < 3:
        score -= 1
        reasons.append(f"Weak contact quality: {stats.barrel_pct:.1f}% Barrel")

    if stats.hard_hit_pct > 45:
        score += 2
        reasons.append(f"Elite hard contact: {stats.hard_hit_pct:.1f}% Hard Hit")
    elif stats.hard_hit_pct > 40:
        score += 1
        reasons.append(f"Good hard contact: {stats.hard_hit_pct:.1f}% Hard Hit")
    elif stats.hard_hit_pct < 30:
        score -= 1
        reasons.append(f"Soft contact concern: {stats.hard_hit_pct:.1f}% Hard Hit")

    if stats.bb_pct > 12:
        score += 1
        reasons.append(f"Strong plate discipline: {stats.bb_pct:.1f}% BB")

    if stats.k_pct < 18:
        score += 1
        reasons.append(f"Good bat-to-ball skills: {stats.k_pct:.1f}% K")
    elif stats.k_pct > 30:
        score -= 1
        reasons.append(f"Strikeout concern: {stats.k_pct:.1f}% K")

    if stats.sprint_speed is not None and stats.sprint_speed > 29:
        score += 1
        reasons.append(f"Stolen base upside: {stats.sprint_speed:.1f} ft/s sprint speed")

    return score, reasons


def _calculate_pitcher_score(stats: PitcherStats) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    era_gap = stats.era - stats.xera

    if era_gap > 1.0:
        score += 4
        reasons.append(
            f"Significant regression candidate: {stats.era:.2f} ERA vs {stats.xera:.2f} xERA (ERA will drop)"
        )
    elif era_gap > 0.5:
        score += 2
        reasons.append(
            f"Moderate regression candidate: {stats.era:.2f} ERA vs {stats.xera:.2f} xERA"
        )
    elif era_gap < -1.0:
        score -= 2
        reasons.append(
            f"WARNING: Overperforming, ERA will rise: {stats.era:.2f} ERA vs {stats.xera:.2f} xERA"
        )

    fip_gap = stats.fip - stats.xfip
    if fip_gap > 0.5:
        score += 1
        reasons.append(
            f"Additional regression signal: {stats.fip:.2f} FIP vs {stats.xfip:.2f} xFIP"
        )

    if stats.k_pct > 28:
        score += 3
        reasons.append(f"Elite strikeout ability: {stats.k_pct:.1f}% K")
    elif stats.k_pct > 24:
        score += 2
        reasons.append(f"Strong strikeout ability: {stats.k_pct:.1f}% K")
    elif stats.k_pct > 20:
        score += 1
        reasons.append(f"Good strikeout ability: {stats.k_pct:.1f}% K")
    elif stats.k_pct < 15:
        score -= 1
        reasons.append(f"Low strikeout rate: {stats.k_pct:.1f}% K")

    if stats.bb_pct < 6:
        score += 2
        reasons.append(f"Elite control: {stats.bb_pct:.1f}% BB")
    elif stats.bb_pct < 8:
        score += 1
        reasons.append(f"Good control: {stats.bb_pct:.1f}% BB")
    elif stats.bb_pct > 12:
        score -= 2
        reasons.append(f"Poor control: {stats.bb_pct:.1f}% BB")

    if stats.barrel_pct_against < 5:
        score += 2
        reasons.append(f"Suppresses hard contact: {stats.barrel_pct_against:.1f}% Barrel against")
    elif stats.barrel_pct_against < 7:
        score += 1
        reasons.append(f"Limits hard contact: {stats.barrel_pct_against:.1f}% Barrel against")
    elif stats.barrel_pct_against > 10:
        score -= 1
        reasons.append(f"Gives up hard contact: {stats.barrel_pct_against:.1f}% Barrel against")

    if stats.position == "SP":
        if stats.innings_pitched > 150:
            score += 1
            reasons.append(f"Durable workload: {stats.innings_pitched:.1f} IP")
        elif stats.innings_pitched < 100:
            score -= 1
            reasons.append(f"Workload concern: {stats.innings_pitched:.1f} IP")

    return score, reasons


def _apply_rank_disparity_batter(
    score: float, reasons: list[str], ops: float, yahoo_rank: int | None, games: int
) -> tuple[float, list[str]]:
    if yahoo_rank is None or games < 10:
        return score, reasons

    if ops >= 0.900:
        expected_rank = 30
    elif ops >= 0.800:
        expected_rank = 60
    elif ops >= 0.700:
        expected_rank = 120
    elif ops >= 0.600:
        expected_rank = 180
    else:
        expected_rank = 250

    rank_disparity = yahoo_rank - expected_rank

    if rank_disparity > 50:
        score += 2
        reasons.append(
            f"Significantly underranked: rank {yahoo_rank} but {ops:.3f} OPS suggests ~{expected_rank}"
        )
    elif rank_disparity > 25:
        score += 1
        reasons.append(
            f"Underranked: rank {yahoo_rank} but {ops:.3f} OPS suggests ~{expected_rank}"
        )
    elif rank_disparity < -40:
        score -= 1
        reasons.append(
            f"Overranked: rank {yahoo_rank} but {ops:.3f} OPS suggests ~{expected_rank}"
        )

    return score, reasons


def _apply_rank_disparity_pitcher(
    score: float, reasons: list[str], era: float, yahoo_rank: int | None, games: int
) -> tuple[float, list[str]]:
    if yahoo_rank is None or games < 5:
        return score, reasons

    if era < 2.50:
        expected_rank = 20
    elif era < 3.00:
        expected_rank = 50
    elif era < 3.50:
        expected_rank = 80
    elif era < 4.00:
        expected_rank = 130
    else:
        expected_rank = 200

    rank_disparity = yahoo_rank - expected_rank

    if rank_disparity > 50:
        score += 2
        reasons.append(
            f"Significantly underranked: rank {yahoo_rank} but {era:.2f} ERA suggests ~{expected_rank}"
        )
    elif rank_disparity > 25:
        score += 1
        reasons.append(
            f"Underranked: rank {yahoo_rank} but {era:.2f} ERA suggests ~{expected_rank}"
        )
    elif rank_disparity < -40:
        score -= 1
        reasons.append(
            f"Overranked: rank {yahoo_rank} but {era:.2f} ERA suggests ~{expected_rank}"
        )

    return score, reasons


def _apply_schedule(
    score: float,
    reasons: list[str],
    games_this_week: int | None,
    games_next_week: int | None,
) -> tuple[float, list[str]]:
    if games_this_week is None or games_next_week is None:
        return score, reasons

    total_upcoming = games_this_week + games_next_week

    if total_upcoming >= 13:
        score += 1
        reasons.append(
            f"Favorable schedule: {games_this_week} games this week, {games_next_week} next week"
        )
    elif total_upcoming < 10:
        score -= 0.5
        reasons.append(
            f"Light schedule: {games_this_week} games this week, {games_next_week} next week"
        )

    return score, reasons


def _enrich_with_yahoo(
    user_email: str, league_id: str, player_name: str
) -> tuple[dict[str, str | int | None], list[str]]:
    yahoo_fields: dict[str, str | int | None] = {}
    warnings: list[str] = []

    try:
        yahoo_response = get_player_season_rank(
            user_email=user_email,
            league_id=league_id,
            player_name=player_name,
        )
        yahoo_data = json.loads(yahoo_response)

        if yahoo_data.get("player"):
            yahoo_player = yahoo_data["player"]
            yahoo_fields = {
                "yahoo_rank": yahoo_player.get("rank"),
                "yahoo_player_key": yahoo_player.get("player_key"),
                "ownership_type": yahoo_player.get("ownership_type"),
                "owner_team_name": yahoo_player.get("owner_team_name"),
                "percent_owned": yahoo_player.get("percent_owned"),
                "injury_status": yahoo_player.get("injury_status"),
            }
        else:
            warnings.append(f"Yahoo rank not found: {yahoo_data.get('error', 'unknown')}")
    except Exception as e:
        warnings.append(f"Yahoo rank lookup failed: {e!s}")
        logger.error(f"{player_name}: Yahoo rank lookup failed: {e!s}")

    return yahoo_fields, warnings


def _enrich_with_schedule(
    team: str, player_name: str
) -> tuple[dict[str, int | None], list[str]]:
    schedule_fields: dict[str, int | None] = {}
    warnings: list[str] = []

    try:
        schedule_response = get_team_schedule([team])
        schedule_data = json.loads(schedule_response)

        if team in schedule_data:
            team_schedule = schedule_data[team]
            if team_schedule.get("status") == "success":
                schedule_fields = {
                    "games_remaining_this_week": team_schedule.get("this_week_games"),
                    "games_next_week": team_schedule.get("next_week_games"),
                }
            else:
                warnings.append(f"Schedule not available: {team_schedule.get('message', 'unknown')}")
    except Exception as e:
        warnings.append(f"Schedule fetch failed: {e!s}")
        logger.error(f"{player_name}: Schedule fetch failed: {e!s}")

    return schedule_fields, warnings


def _score_batter(
    stats: BatterStats, user_email: str, league_id: str
) -> str:
    score, reasons = _calculate_batter_score(stats)

    result: dict[str, str | int | float | list[str] | None] = {
        "status": "success",
        "name": stats.player_name,
        "team": stats.team,
        "position": stats.position,
        "games_played": stats.games_played,
        "batting_avg": stats.batting_avg,
        "obp": stats.obp,
        "slg": stats.slg,
        "ops": stats.ops,
        "woba": stats.woba,
        "xwoba": stats.xwoba,
        "woba_gap": round(stats.xwoba - stats.woba, 3),
        "barrel_pct": stats.barrel_pct,
        "hard_hit_pct": stats.hard_hit_pct,
        "k_pct": stats.k_pct,
        "bb_pct": stats.bb_pct,
        "sprint_speed": stats.sprint_speed,
        "hr": stats.hr,
        "rbi": stats.rbi,
        "sb": stats.sb,
        "runs": stats.runs,
    }

    warnings: list[str] = []

    yahoo_fields, yahoo_warnings = _enrich_with_yahoo(user_email, league_id, stats.player_name)
    result.update(yahoo_fields)
    warnings.extend(yahoo_warnings)

    schedule_fields, schedule_warnings = _enrich_with_schedule(stats.team, stats.player_name)
    result.update(schedule_fields)
    warnings.extend(schedule_warnings)

    yahoo_rank_val = yahoo_fields.get("yahoo_rank")
    yahoo_rank = int(yahoo_rank_val) if yahoo_rank_val is not None else None
    score, reasons = _apply_rank_disparity_batter(
        score, reasons, stats.ops, yahoo_rank, stats.games_played
    )

    games_this = schedule_fields.get("games_remaining_this_week")
    games_next = schedule_fields.get("games_next_week")
    score, reasons = _apply_schedule(score, reasons, games_this, games_next)

    result["undervalued_score"] = score
    result["undervalued_reasons"] = reasons

    if warnings:
        result["warnings"] = warnings

    return json.dumps(result, indent=2)


def _score_pitcher(
    stats: PitcherStats, user_email: str, league_id: str
) -> str:
    score, reasons = _calculate_pitcher_score(stats)

    result: dict[str, str | int | float | list[str] | None] = {
        "status": "success",
        "name": stats.player_name,
        "team": stats.team,
        "position": stats.position,
        "games_played": stats.games_played,
        "era": stats.era,
        "xera": stats.xera,
        "era_gap": round(stats.era - stats.xera, 2),
        "fip": stats.fip,
        "xfip": stats.xfip,
        "whip": stats.whip,
        "k_pct": stats.k_pct,
        "bb_pct": stats.bb_pct,
        "barrel_pct_against": stats.barrel_pct_against,
        "hard_hit_pct_against": stats.hard_hit_pct_against,
        "innings_pitched": stats.innings_pitched,
        "wins": stats.wins,
        "saves": stats.saves,
    }

    warnings: list[str] = []

    yahoo_fields, yahoo_warnings = _enrich_with_yahoo(user_email, league_id, stats.player_name)
    result.update(yahoo_fields)
    warnings.extend(yahoo_warnings)

    schedule_fields, schedule_warnings = _enrich_with_schedule(stats.team, stats.player_name)
    result.update(schedule_fields)
    warnings.extend(schedule_warnings)

    yahoo_rank_val = yahoo_fields.get("yahoo_rank")
    yahoo_rank = int(yahoo_rank_val) if yahoo_rank_val is not None else None
    score, reasons = _apply_rank_disparity_pitcher(
        score, reasons, stats.era, yahoo_rank, stats.games_played
    )

    games_this = schedule_fields.get("games_remaining_this_week")
    games_next = schedule_fields.get("games_next_week")
    score, reasons = _apply_schedule(score, reasons, games_this, games_next)

    result["undervalued_score"] = score
    result["undervalued_reasons"] = reasons

    if warnings:
        result["warnings"] = warnings

    return json.dumps(result, indent=2)


@tool(args_schema=CalculateMLBUndervaluedInput)
def calculate_mlb_undervalued_score(
    user_email: str,
    league_id: str,
    batter_stats: BatterStats | None = None,
    pitcher_stats: PitcherStats | None = None,
) -> str:
    """Calculate an undervalued score for an MLB player using pre-fetched stats.

    This tool takes stats you already fetched via query_stats_db (with sport='baseball')
    and enriches them with Yahoo fantasy league rank, ownership info, and team schedule.

    Provide exactly one of batter_stats or pitcher_stats.

    Score interpretation:
    - > 5: Highly undervalued — STRONG BUY
    - 3-5: Moderately undervalued — good target
    - 0-3: Fairly valued
    - < 0: OVERVALUED — avoid acquiring

    You MUST first use query_stats_db to get the player's stats, then pass them here.
    """
    if batter_stats is not None and pitcher_stats is not None:
        return json.dumps({"error": "Provide exactly one of batter_stats or pitcher_stats, not both"})
    if batter_stats is None and pitcher_stats is None:
        return json.dumps({"error": "Provide exactly one of batter_stats or pitcher_stats"})

    if batter_stats is not None:
        return _score_batter(batter_stats, user_email, league_id)

    assert pitcher_stats is not None
    return _score_pitcher(pitcher_stats, user_email, league_id)
