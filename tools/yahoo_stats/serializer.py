"""Centralized serialization for yfpy objects returned by the Yahoo Fantasy API."""

from collections.abc import Mapping, Sequence

SerializedDict = dict[str, "str | int | float | bool | None | list[SerializedDict] | SerializedDict"]


def _decode_name(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw) if raw is not None else "Unknown"


def _getattr_safe(obj: object, attr: str) -> str | int | float | None:
    val = getattr(obj, attr, None)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, (str, int, float)):
        return val
    if val is None:
        return None
    return str(val)


def serialize_player(player: object) -> SerializedDict:
    name_obj = getattr(player, "name", None)
    if name_obj and hasattr(name_obj, "full"):
        player_name = _decode_name(name_obj.full)
    elif name_obj:
        player_name = _decode_name(name_obj)
    else:
        player_name = "Unknown"

    player_stats = getattr(player, "player_stats", None)
    total_points = _getattr_safe(player_stats, "total_points") if player_stats else None

    stats_list: list[SerializedDict] = []
    if player_stats:
        raw_stats = getattr(player_stats, "stats", None)
        if isinstance(raw_stats, list):
            for stat in raw_stats:
                stat_id = _getattr_safe(stat, "stat_id")
                value = _getattr_safe(stat, "value")
                if stat_id is not None:
                    stats_list.append({"stat_id": stat_id, "value": value})

    player_points = getattr(player, "player_points", None)
    points_total = _getattr_safe(player_points, "total") if player_points else None

    result: SerializedDict = {
        "name": player_name,
        "player_key": _getattr_safe(player, "player_key"),
        "player_id": _getattr_safe(player, "player_id"),
        "position": _getattr_safe(player, "display_position"),
        "nhl_team": _getattr_safe(player, "editorial_team_abbr"),
        "nhl_team_full": _getattr_safe(player, "editorial_team_full_name"),
        "status": _getattr_safe(player, "status"),
        "injury_status": _getattr_safe(player, "status_full"),
        "fantasy_points": total_points,
        "points_total": points_total,
    }
    if stats_list:
        result["stats"] = stats_list
    return result


def serialize_team(team: object) -> SerializedDict:
    name = _getattr_safe(team, "name")
    team_name = _decode_name(name) if name else "Unknown"

    standings = getattr(team, "team_standings", None)
    wins = _getattr_safe(standings, "wins") if standings else None
    losses = _getattr_safe(standings, "losses") if standings else None
    ties = _getattr_safe(standings, "ties") if standings else None
    points_for = _getattr_safe(standings, "points_for") if standings else None
    points_against = _getattr_safe(standings, "points_against") if standings else None
    rank = _getattr_safe(standings, "rank") if standings else None

    managers = getattr(team, "managers", None)
    manager_name: str | None = None
    if managers and isinstance(managers, list) and len(managers) > 0:
        manager_name = _decode_name(getattr(managers[0], "nickname", None))

    return {
        "team_id": _getattr_safe(team, "team_id"),
        "team_key": _getattr_safe(team, "team_key"),
        "name": team_name,
        "manager": manager_name,
        "waiver_priority": _getattr_safe(team, "waiver_priority"),
        "number_of_moves": _getattr_safe(team, "number_of_moves"),
        "number_of_trades": _getattr_safe(team, "number_of_trades"),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "points_for": points_for,
        "points_against": points_against,
        "rank": rank,
    }


def serialize_matchup(matchup: object) -> SerializedDict:
    teams_data: list[SerializedDict] = []
    matchup_teams = getattr(matchup, "teams", None)
    if isinstance(matchup_teams, list):
        for team in matchup_teams:
            team_info: SerializedDict = {
                "team_key": _getattr_safe(team, "team_key"),
                "name": _decode_name(_getattr_safe(team, "name")),
            }
            team_points = getattr(team, "team_points", None)
            if team_points:
                team_info["points"] = _getattr_safe(team_points, "total")
            team_proj = getattr(team, "team_projected_points", None)
            if team_proj:
                team_info["projected_points"] = _getattr_safe(team_proj, "total")
            teams_data.append(team_info)

    return {
        "week": _getattr_safe(matchup, "week"),
        "status": _getattr_safe(matchup, "status"),
        "winner_team_key": _getattr_safe(matchup, "winner_team_key"),
        "teams": teams_data,
    }


def serialize_league_info(league_info: object) -> SerializedDict:
    fields = [
        "current_week", "start_week", "end_week", "start_date", "end_date",
        "season", "name", "league_key", "league_id", "num_teams",
        "scoring_type", "game_code", "url",
    ]
    result: SerializedDict = {}
    for field in fields:
        val = _getattr_safe(league_info, field)
        if val is not None:
            result[field] = val
    return result


def serialize_draft_pick(pick: object) -> SerializedDict:
    return {
        "pick": _getattr_safe(pick, "pick"),
        "round": _getattr_safe(pick, "round"),
        "team_key": _getattr_safe(pick, "team_key"),
        "player_key": _getattr_safe(pick, "player_key"),
    }


def serialize_transaction(transaction: object) -> SerializedDict:
    players_data: list[SerializedDict] = []
    tx_players = getattr(transaction, "players", None)
    if isinstance(tx_players, list):
        for p in tx_players:
            p_name_obj = getattr(p, "name", None)
            if p_name_obj and hasattr(p_name_obj, "full"):
                p_name = _decode_name(p_name_obj.full)
            elif p_name_obj:
                p_name = _decode_name(p_name_obj)
            else:
                p_name = "Unknown"
            players_data.append({
                "player_key": _getattr_safe(p, "player_key"),
                "name": p_name,
                "type": _getattr_safe(p, "transaction_data"),
            })

    return {
        "transaction_key": _getattr_safe(transaction, "transaction_key"),
        "type": _getattr_safe(transaction, "type"),
        "timestamp": _getattr_safe(transaction, "timestamp"),
        "status": _getattr_safe(transaction, "status"),
        "players": players_data,
    }


def serialize_generic(obj: object) -> object:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, list):
        return [serialize_generic(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): serialize_generic(v) for k, v in obj.items()}
    if isinstance(obj, Mapping):
        return {str(k): serialize_generic(v) for k, v in obj.items()}
    if isinstance(obj, Sequence):
        return [serialize_generic(item) for item in obj]

    result: dict[str, object] = {}
    for attr in dir(obj):
        if attr.startswith("_"):
            continue
        if callable(getattr(obj, attr, None)):
            continue
        val = getattr(obj, attr, None)
        if isinstance(val, (str, int, float, bool, type(None))):
            result[attr] = val
        elif isinstance(val, bytes):
            result[attr] = val.decode("utf-8", errors="replace")
        elif isinstance(val, list):
            result[attr] = [serialize_generic(item) for item in val]
    return result if result else str(obj)
