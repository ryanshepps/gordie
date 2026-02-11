"""Tool to fetch team matchup data from Yahoo Fantasy."""

from client.authenticated_yahoo_client import AuthenticatedYahooClient
from data.pydantic_models import CurrentMatchup, Matchup, MatchupOpponent, MatchupResponse
from module.logger import get_logger

logger = get_logger(__name__)


def get_team_matchups(user_email: str, league_id: str, team_id: str) -> MatchupResponse:
    """
    Get all matchups for a fantasy team.

    Args:
        user_email: User's email for Yahoo authentication
        league_id: Yahoo league ID
        team_id: Yahoo team ID

    Returns:
        MatchupResponse with list of matchups including opponent info
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        matchups = yahoo_client.query.get_team_matchups(team_id)

        result: list[Matchup] = []
        for matchup in matchups:
            week = getattr(matchup, "week", None)
            teams = getattr(matchup, "teams", [])

            # Find opponent (the team that isn't ours)
            opponent = None
            for team in teams:
                team_key = getattr(team, "team_key", "")
                if not team_key.endswith(f".t.{team_id}"):
                    standings = getattr(team, "team_standings", None)
                    opponent = MatchupOpponent(
                        name=getattr(team, "name", "Unknown"),
                        team_key=team_key,
                        wins=getattr(standings, "wins", 0) if standings else 0,
                        losses=getattr(standings, "losses", 0) if standings else 0,
                        ties=getattr(standings, "ties", 0) if standings else 0,
                    )
                    break

            result.append(
                Matchup(
                    week=int(week) if week else 0,
                    week_start=getattr(matchup, "week_start", ""),
                    week_end=getattr(matchup, "week_end", ""),
                    status=getattr(matchup, "status", ""),
                    opponent=opponent,
                )
            )

        return MatchupResponse(matchups=result, count=len(result))

    except Exception as e:
        logger.error(f"Error fetching team matchups: {e}")
        return MatchupResponse(error=str(e))


def get_current_matchup(user_email: str, league_id: str, team_id: str) -> CurrentMatchup | None:
    """
    Get the current week's matchup for a team.

    Args:
        user_email: User's email for Yahoo authentication
        league_id: Yahoo league ID
        team_id: Yahoo team ID

    Returns:
        CurrentMatchup with opponent name, record, week dates, or None if not found
    """
    yahoo_client = AuthenticatedYahooClient(league_id=int(league_id), user_email=user_email)

    try:
        # Get current week from league info
        league_info = yahoo_client.query.get_league_info()
        current_week = int(getattr(league_info, "current_week", 1))

        response = get_team_matchups(user_email, league_id, team_id)

        if response.error:
            logger.warning(f"Matchup fetch had error: {response.error}")
            return None

        for matchup in response.matchups:
            if matchup.week == current_week and matchup.opponent:
                return CurrentMatchup(
                    opponent_name=matchup.opponent.name,
                    opponent_record=matchup.opponent.record,
                    week=current_week,
                    week_start=matchup.week_start,
                    week_end=matchup.week_end,
                )

        return None

    except Exception as e:
        logger.warning(f"Could not get current matchup: {e}")
        return None
