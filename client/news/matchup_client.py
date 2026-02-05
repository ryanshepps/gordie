"""Matchup client for fetching today's games and opponent strength.

Fetches game-day schedule from NHL API and calculates opponent weakness
metrics based on goals against average.
"""

from __future__ import annotations

from datetime import datetime

from nhlpy import NHLClient

from agent.news.news_digest import MatchupAlert
from module.logger import get_logger

logger = get_logger(__name__)

# Goals against average threshold for "weak" opponent
WEAK_OPPONENT_GAA_THRESHOLD = 3.2


def fetch_matchups() -> list[MatchupAlert]:
    """Fetch matchup alerts for today's NHL games.

    Identifies players facing teams with high goals against average,
    which represents favorable scoring opportunities.

    Returns:
        List of MatchupAlert objects for players with favorable matchups

    Note:
        Returns empty list on fetch failure rather than raising exception
        to allow the news digest to proceed with partial data.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return fetch_matchups_for_date(today)


def fetch_matchups_for_date(date_str: str) -> list[MatchupAlert]:
    """Fetch matchup alerts for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of MatchupAlert objects
    """
    client = NHLClient()

    try:
        schedule = client.schedule.daily_schedule(date_str)
    except Exception as e:
        logger.warning(f"Failed to fetch NHL schedule for {date_str}: {e}")
        return []

    if not schedule or "games" not in schedule:
        logger.info(f"No games scheduled for {date_str}")
        return []

    games = schedule["games"]
    if not games:
        logger.info(f"No games found for {date_str}")
        return []

    logger.info(f"Found {len(games)} games for {date_str}")

    # Collect team stats for all games
    matchups: list[MatchupAlert] = []
    team_gaa_cache: dict[str, float] = {}

    for game in games:
        try:
            home_team = game.get("homeTeam", {})
            away_team = game.get("awayTeam", {})

            home_abbrev = home_team.get("abbrev", "")
            away_abbrev = away_team.get("abbrev", "")

            # Get GAA for each team (caching to avoid duplicate lookups)
            home_gaa = team_gaa_cache.get(home_abbrev)
            if home_gaa is None:
                home_gaa = _get_team_goals_against_avg(client, home_abbrev)
                team_gaa_cache[home_abbrev] = home_gaa

            away_gaa = team_gaa_cache.get(away_abbrev)
            if away_gaa is None:
                away_gaa = _get_team_goals_against_avg(client, away_abbrev)
                team_gaa_cache[away_abbrev] = away_gaa

            # Check if away team faces a weak defense (high GAA home team)
            if home_gaa >= WEAK_OPPONENT_GAA_THRESHOLD:
                # Get away team roster for favorable matchup alerts
                away_roster = _get_team_top_players(client, away_abbrev)
                for player_name in away_roster:
                    matchups.append(
                        MatchupAlert(
                            player_name=player_name,
                            opponent=home_abbrev,
                            opponent_goals_against_avg=home_gaa,
                        )
                    )

            # Check if home team faces a weak defense (high GAA away team)
            if away_gaa >= WEAK_OPPONENT_GAA_THRESHOLD:
                home_roster = _get_team_top_players(client, home_abbrev)
                for player_name in home_roster:
                    matchups.append(
                        MatchupAlert(
                            player_name=player_name,
                            opponent=away_abbrev,
                            opponent_goals_against_avg=away_gaa,
                        )
                    )

        except Exception as e:
            logger.warning(f"Error processing game: {e}")
            continue

    logger.info(f"Generated {len(matchups)} matchup alerts for {date_str}")
    return matchups


def _get_team_goals_against_avg(client: NHLClient, team_abbrev: str) -> float:
    """Get team's goals against average from standings.

    Args:
        client: NHLClient instance
        team_abbrev: Team abbreviation (e.g., "TOR")

    Returns:
        Goals against average, or 3.0 (league average) if unavailable
    """
    try:
        standings = client.standings.league_standings()

        if not standings or "standings" not in standings:
            return 3.0

        for team in standings["standings"]:
            # teamAbbrev is nested: {"default": "TOR"}
            abbrev = team.get("teamAbbrev", {}).get("default", "")
            if abbrev == team_abbrev:
                # Field is "goalAgainst" (singular), not "goalsAgainst"
                goals_against = team.get("goalAgainst", 0)
                games_played = team.get("gamesPlayed", 1)
                if games_played > 0:
                    return round(goals_against / games_played, 2)

        return 3.0

    except Exception as e:
        logger.warning(f"Error fetching GAA for {team_abbrev}: {e}")
        return 3.0


def _get_team_top_players(client: NHLClient, team_abbrev: str) -> list[str]:
    """Get top offensive players for a team.

    Args:
        client: NHLClient instance
        team_abbrev: Team abbreviation (e.g., "TOR")

    Returns:
        List of player names (top scorers on the team)
    """
    try:
        # Get current season
        now = datetime.now()
        season = now.year if now.month >= 10 else now.year - 1
        season_str = f"{season}{season + 1}"

        roster = client.teams.team_roster(team_abbrev, season_str)

        if not roster:
            return []

        # Extract player names from roster
        player_names: list[str] = []
        for position in ["forwards", "defensemen"]:
            players = roster.get(position, [])
            for player in players:
                first_name = player.get("firstName", {}).get("default", "")
                last_name = player.get("lastName", {}).get("default", "")
                if first_name and last_name:
                    player_names.append(f"{first_name} {last_name}")

        return player_names

    except Exception as e:
        logger.warning(f"Error fetching roster for {team_abbrev}: {e}")
        return []
