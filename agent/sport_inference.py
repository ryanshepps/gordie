import re
from datetime import UTC, datetime, timedelta

from agent.context_types import Sport

STICKY_TIMEOUT = timedelta(minutes=5)

SPORT_KEYWORDS: dict[Sport, list[str]] = {
    "nhl": [
        "hockey",
        "nhl",
        "ice hockey",
        "goalie",
        "power play",
        "corsi",
        "fenwick",
        "hat trick",
    ],
    "mlb": [
        "baseball",
        "mlb",
        "batting",
        "pitcher",
        "pitching",
        "home run",
        "era",
        "strikeout",
        "inning",
        "bullpen",
        "ops",
        "whip",
    ],
    "nfl": [
        "football",
        "nfl",
        "quarterback",
        "touchdown",
        "rushing",
        "wide receiver",
        "tight end",
        "snap count",
        "redzone",
        "sack",
    ],
    "nba": [
        "basketball",
        "nba",
        "three pointer",
        "rebound",
        "dunk",
        "free throw",
        "double double",
        "triple double",
        "block",
    ],
}

_KEYWORD_PATTERNS: dict[Sport, list[re.Pattern[str]]] = {
    sport: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords]
    for sport, keywords in SPORT_KEYWORDS.items()
}


def _user_sports(user_teams: list[dict[str, str]]) -> set[Sport]:
    sports: set[Sport] = set()
    for team in user_teams:
        sport = team.get("sport")
        if sport in ("nhl", "mlb", "nfl", "nba"):
            sports.add(sport)  # type: ignore[arg-type]
    return sports


def _match_keywords(message_text: str, eligible_sports: set[Sport]) -> Sport | None:
    matched: list[Sport] = []
    for sport in eligible_sports:
        patterns = _KEYWORD_PATTERNS.get(sport, [])
        if any(pattern.search(message_text) for pattern in patterns):
            matched.append(sport)
    if len(matched) == 1:
        return matched[0]
    return None


def _match_team_names(
    message_text: str, user_teams: list[dict[str, str]]
) -> Sport | None:
    text_lower = message_text.lower()
    matched_sports: set[Sport] = set()
    for team in user_teams:
        team_name = team.get("team_name", "").lower()
        league_name = team.get("league_name", "").lower()
        sport = team.get("sport")
        if sport not in ("nhl", "mlb", "nfl", "nba"):
            continue
        if (team_name and team_name in text_lower) or (
            league_name and league_name in text_lower
        ):
            matched_sports.add(sport)  # type: ignore[arg-type]
    if len(matched_sports) == 1:
        return matched_sports.pop()
    return None


def _is_within_sticky_timeout(sport_inferred_at: str | None) -> bool:
    if not sport_inferred_at:
        return False
    try:
        inferred_time = datetime.fromisoformat(sport_inferred_at)
        return datetime.now(UTC) - inferred_time < STICKY_TIMEOUT
    except ValueError:
        return False


def infer_sport(
    message_text: str,
    user_teams: list[dict[str, str]],
    current_sport: Sport | None,
    sport_inferred_at: str | None,
) -> Sport | None:
    if len(user_teams) == 1:
        sport = user_teams[0].get("sport")
        if sport in ("nhl", "mlb", "nfl", "nba"):
            return sport  # type: ignore[return-value]
        return None

    if current_sport and _is_within_sticky_timeout(sport_inferred_at):
        return current_sport

    eligible_sports = _user_sports(user_teams)

    keyword_match = _match_keywords(message_text, eligible_sports)
    if keyword_match:
        return keyword_match

    name_match = _match_team_names(message_text, user_teams)
    if name_match:
        return name_match

    if current_sport and current_sport in eligible_sports:
        return current_sport

    return None
