from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from gordie.agent.context_types import Sport
from gordie.agent.news.news_digest import InjuryAlert, MatchupAlert, TradeAlert
from gordie.client.news.espn_client import fetch_injuries
from gordie.client.news.matchup_client import fetch_matchups
from gordie.client.news.schedule_client import fetch_teams_playing_today
from gordie.client.news.transactions_client import fetch_trades


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

_REGISTRY: dict[Sport, NewsClientBundle] = {
    "nhl": _NHL_CLIENTS,
}


def get_news_clients(sport: Sport) -> NewsClientBundle:
    clients = _REGISTRY.get(sport)
    if clients is None:
        raise ValueError(f"No news clients registered for sport: {sport}")
    return clients
