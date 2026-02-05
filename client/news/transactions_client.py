"""Transactions client for fetching NHL trade news.

Fetches trade updates from various RSS sources and parses them
into structured TradeAlert objects.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from agent.news.news_digest import TradeAlert
from module.logger import get_logger

logger = get_logger(__name__)

# RSS feed URLs for trade news
# Using NHL official and sports news feeds since PuckPedia/CapFriendly
# may have rate limits or require authentication
TRADE_RSS_URLS = [
    "https://www.nhl.com/rss/news.xml",
]

# Patterns for extracting trade information
TRADE_PATTERNS = [
    r"(?P<player>[\w\s\.\-']+)\s+traded\s+(?:from\s+)?(?P<from>[\w\s]+)\s+to\s+(?P<to>[\w\s]+)",
    r"(?P<from>[\w\s]+)\s+trade\s+(?P<player>[\w\s\.\-']+)\s+to\s+(?P<to>[\w\s]+)",
    r"(?P<to>[\w\s]+)\s+acquire\s+(?P<player>[\w\s\.\-']+)\s+from\s+(?P<from>[\w\s]+)",
]

# NHL team name normalization
TEAM_ABBREVIATIONS = {
    "anaheim ducks": "ANA",
    "arizona coyotes": "ARI",
    "utah hockey club": "UTA",
    "boston bruins": "BOS",
    "buffalo sabres": "BUF",
    "calgary flames": "CGY",
    "carolina hurricanes": "CAR",
    "chicago blackhawks": "CHI",
    "colorado avalanche": "COL",
    "columbus blue jackets": "CBJ",
    "dallas stars": "DAL",
    "detroit red wings": "DET",
    "edmonton oilers": "EDM",
    "florida panthers": "FLA",
    "los angeles kings": "LAK",
    "minnesota wild": "MIN",
    "montreal canadiens": "MTL",
    "nashville predators": "NSH",
    "new jersey devils": "NJD",
    "new york islanders": "NYI",
    "new york rangers": "NYR",
    "ottawa senators": "OTT",
    "philadelphia flyers": "PHI",
    "pittsburgh penguins": "PIT",
    "san jose sharks": "SJS",
    "seattle kraken": "SEA",
    "st. louis blues": "STL",
    "tampa bay lightning": "TBL",
    "toronto maple leafs": "TOR",
    "vancouver canucks": "VAN",
    "vegas golden knights": "VGK",
    "washington capitals": "WSH",
    "winnipeg jets": "WPG",
}


def fetch_trades() -> list[TradeAlert]:
    """Fetch trade alerts from NHL news RSS feeds.

    Returns:
        List of TradeAlert objects parsed from the RSS feeds

    Note:
        Returns empty list on fetch failure rather than raising exception
        to allow the news digest to proceed with partial data.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    all_trades: list[TradeAlert] = []

    for url in TRADE_RSS_URLS:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            trades = _parse_rss_feed(response.text)
            all_trades.extend(trades)
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch trade RSS from {url}: {e}")
            continue

    # Deduplicate by player name
    seen_players: set[str] = set()
    unique_trades: list[TradeAlert] = []
    for trade in all_trades:
        key = trade.player_name.lower()
        if key not in seen_players:
            seen_players.add(key)
            unique_trades.append(trade)

    logger.info(f"Parsed {len(unique_trades)} trade alerts from RSS feeds")
    return unique_trades


def _parse_rss_feed(xml_content: str) -> list[TradeAlert]:
    """Parse RSS XML content into TradeAlert objects.

    Args:
        xml_content: Raw XML string from RSS feed

    Returns:
        List of TradeAlert objects
    """
    alerts: list[TradeAlert] = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.warning(f"Failed to parse trade RSS XML: {e}")
        return alerts

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        desc_elem = item.find("description")
        pub_date_elem = item.find("pubDate")

        if title_elem is None:
            continue

        title = title_elem.text or ""
        description = desc_elem.text or "" if desc_elem is not None else ""
        pub_date = pub_date_elem.text or "" if pub_date_elem is not None else ""

        # Only process items that look like trade news
        combined = f"{title} {description}".lower()
        if not any(word in combined for word in ["trade", "traded", "acquire", "acquired"]):
            continue

        alert = _extract_trade_alert(title, description, pub_date)
        if alert:
            alerts.append(alert)

    return alerts


def _extract_trade_alert(title: str, description: str, pub_date: str) -> TradeAlert | None:
    """Extract trade alert from RSS item text.

    Args:
        title: RSS item title
        description: RSS item description
        pub_date: RSS item publication date

    Returns:
        TradeAlert if trade info found, None otherwise
    """
    combined_text = f"{title} {description}"

    for pattern in TRADE_PATTERNS:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            groups = match.groupdict()
            player_name = groups.get("player", "").strip()
            from_team = groups.get("from", "").strip()
            to_team = groups.get("to", "").strip()

            if not player_name or not from_team or not to_team:
                continue

            return TradeAlert(
                player_name=player_name,
                from_team=_normalize_team(from_team),
                to_team=_normalize_team(to_team),
                trade_date=_parse_date(pub_date),
            )

    return None


def _normalize_team(team_name: str) -> str:
    """Normalize team name to abbreviation.

    Args:
        team_name: Raw team name from RSS

    Returns:
        Team abbreviation (e.g., "TOR") or cleaned name if not found
    """
    normalized = team_name.lower().strip()

    # Check direct match
    if normalized in TEAM_ABBREVIATIONS:
        return TEAM_ABBREVIATIONS[normalized]

    # Check if it's already an abbreviation
    if team_name.upper() in TEAM_ABBREVIATIONS.values():
        return team_name.upper()

    # Check partial match
    for full_name, abbr in TEAM_ABBREVIATIONS.items():
        if normalized in full_name or full_name in normalized:
            return abbr

    # Return cleaned version if no match
    return team_name.upper()[:3]


def _parse_date(pub_date: str) -> str:
    """Parse RSS pub date into ISO format.

    Args:
        pub_date: RSS publication date string

    Returns:
        ISO format date string (YYYY-MM-DD)
    """
    if not pub_date:
        return datetime.now().strftime("%Y-%m-%d")

    try:
        # RSS dates are typically in RFC 2822 format
        # e.g., "Mon, 15 Jan 2024 10:30:00 GMT"
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(pub_date)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now().strftime("%Y-%m-%d")
