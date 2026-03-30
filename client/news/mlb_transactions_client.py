from __future__ import annotations

from datetime import datetime, timedelta

import requests

from agent.news.news_digest import TradeAlert
from client.teams.mlb_teams import MLB_TEAMS
from module.logger import get_logger

logger = get_logger(__name__)

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

_TEAM_ID_TO_ABBR: dict[int, str] = {}


def _build_team_id_map() -> None:
    if _TEAM_ID_TO_ABBR:
        return

    try:
        response = requests.get(f"{MLB_API_BASE}/teams?sportId=1", timeout=15)
        response.raise_for_status()
        data = response.json()

        for team in data.get("teams", []):
            team_id = team.get("id")
            abbr = team.get("abbreviation", "")
            if team_id and abbr:
                _TEAM_ID_TO_ABBR[team_id] = abbr
    except requests.RequestException as e:
        logger.warning(f"Failed to build MLB team ID map: {e}")

        for abbr in MLB_TEAMS:
            _TEAM_ID_TO_ABBR[0] = abbr


def fetch_mlb_trades() -> list[TradeAlert]:
    _build_team_id_map()

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    url = (
        f"{MLB_API_BASE}/transactions"
        f"?startDate={start_date}&endDate={end_date}"
        f"&transactionTypes=Trade"
    )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch MLB transactions: {e}")
        return []

    trades: list[TradeAlert] = []
    seen_players: set[str] = set()

    for txn in data.get("transactions", []):
        player_info = txn.get("person", {})
        player_name = player_info.get("fullName", "")

        if not player_name:
            continue

        key = player_name.lower()
        if key in seen_players:
            continue
        seen_players.add(key)

        from_team_id = txn.get("fromTeam", {}).get("id")
        to_team_id = txn.get("toTeam", {}).get("id")

        from_abbr = _TEAM_ID_TO_ABBR.get(from_team_id, "") if from_team_id else ""
        to_abbr = _TEAM_ID_TO_ABBR.get(to_team_id, "") if to_team_id else ""

        if not from_abbr or not to_abbr:
            continue

        trade_date_str = txn.get("date", end_date)
        trade_date = _parse_date(trade_date_str)

        trades.append(
            TradeAlert(
                player_name=player_name,
                from_team=from_abbr,
                to_team=to_abbr,
                trade_date=trade_date,
            )
        )

    logger.info(f"Parsed {len(trades)} MLB trade alerts")
    return trades


def _parse_date(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return datetime.now().strftime("%Y-%m-%d")
