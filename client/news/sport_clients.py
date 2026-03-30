from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from agent.context_types import Sport
from agent.news.news_digest import InjuryAlert, MatchupAlert, TradeAlert
from client.news.espn_client import fetch_injuries
from client.news.matchup_client import fetch_matchups
from client.news.mlb_matchup_client import fetch_mlb_matchups
from client.news.mlb_schedule_client import fetch_mlb_teams_playing_today
from client.news.mlb_transactions_client import fetch_mlb_trades
from client.news.schedule_client import fetch_teams_playing_today
from client.news.transactions_client import fetch_trades


@dataclass(frozen=True, slots=True)
class NewsClientBundle:
    fetch_injuries: Callable[[], list[InjuryAlert]]
    fetch_trades: Callable[[], list[TradeAlert]]
    fetch_matchups: Callable[[], list[MatchupAlert]]
    fetch_teams_playing_today: Callable[[], set[str]]


_NHL_CLIENTS = NewsClientBundle(
    fetch_injuries=partial(fetch_injuries, sport="nhl"),
    fetch_trades=fetch_trades,
    fetch_matchups=fetch_matchups,
    fetch_teams_playing_today=fetch_teams_playing_today,
)

_MLB_CLIENTS = NewsClientBundle(
    fetch_injuries=partial(fetch_injuries, sport="mlb"),
    fetch_trades=fetch_mlb_trades,
    fetch_matchups=fetch_mlb_matchups,
    fetch_teams_playing_today=fetch_mlb_teams_playing_today,
)

_REGISTRY: dict[Sport, NewsClientBundle] = {
    "nhl": _NHL_CLIENTS,
    "mlb": _MLB_CLIENTS,
}


def get_news_clients(sport: Sport) -> NewsClientBundle:
    clients = _REGISTRY.get(sport)
    if clients is None:
        raise ValueError(f"No news clients registered for sport: {sport}")
    return clients
