from datetime import UTC, datetime, timedelta

import pytest

from gordie.agent.sport_inference import infer_sport


def _teams(*sports: str) -> list[dict[str, str]]:
    return [
        {
            "league_id": str(i),
            "team_id": str(i),
            "team_name": f"Team {i}",
            "league_name": f"League {i}",
            "sport": sport,
        }
        for i, sport in enumerate(sports, start=1)
    ]


def _teams_with_names(
    entries: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    return [
        {
            "league_id": str(i),
            "team_id": str(i),
            "team_name": team_name,
            "league_name": league_name,
            "sport": sport,
        }
        for i, (sport, team_name, league_name) in enumerate(entries, start=1)
    ]


def _recent_timestamp() -> str:
    return (datetime.now(UTC) - timedelta(minutes=2)).isoformat()


def _stale_timestamp() -> str:
    return (datetime.now(UTC) - timedelta(minutes=10)).isoformat()


class TestSingleTeamShortcut:
    def test_returns_sport_of_single_team(self):
        result = infer_sport("anything", _teams("nfl"), None, None)
        assert result == "nfl"

    def test_returns_none_for_invalid_sport(self):
        teams = [
            {
                "league_id": "1",
                "team_id": "1",
                "team_name": "T",
                "league_name": "L",
                "sport": "curling",
            }
        ]
        result = infer_sport("anything", teams, None, None)
        assert result is None


class TestStickyContext:
    def test_returns_current_sport_within_timeout(self):
        result = infer_sport(
            "some random message",
            _teams("nhl", "nfl"),
            "nhl",
            _recent_timestamp(),
        )
        assert result == "nhl"

    def test_reevaluates_after_timeout(self):
        result = infer_sport(
            "how's my football team doing",
            _teams("nhl", "nfl"),
            "nhl",
            _stale_timestamp(),
        )
        assert result == "nfl"

    def test_no_timestamp_triggers_evaluation(self):
        result = infer_sport(
            "how's my football team doing",
            _teams("nhl", "nfl"),
            "nhl",
            None,
        )
        assert result == "nfl"


class TestKeywordMatching:
    def test_hockey_keyword(self):
        result = infer_sport("my hockey lineup needs help", _teams("nhl", "nfl"), None, None)
        assert result == "nhl"

    def test_football_keyword(self):
        result = infer_sport("who should I start at quarterback", _teams("nfl", "nba"), None, None)
        assert result == "nfl"

    def test_basketball_keyword(self):
        result = infer_sport("need help with my nba roster", _teams("nhl", "nba"), None, None)
        assert result == "nba"

    def test_case_insensitive(self):
        result = infer_sport("HOCKEY is great", _teams("nhl", "nfl"), None, None)
        assert result == "nhl"

    def test_keyword_for_sport_user_doesnt_have_is_ignored(self):
        result = infer_sport("talk about basketball", _teams("nhl", "nfl"), None, None)
        assert result is None

    def test_multiple_sport_keywords_returns_none(self):
        result = infer_sport(
            "should I trade my hockey player for a football player",
            _teams("nhl", "nfl"),
            None,
            None,
        )
        assert result is None

    def test_word_boundary_prevents_false_positive(self):
        result = infer_sport("that was a nice play", _teams("nhl", "nfl"), None, None)
        assert result is None


class TestTeamNameMatching:
    def test_team_name_in_message(self):
        teams = _teams_with_names(
            [
                ("nhl", "Kraken Crushers", "NHL Dynasty"),
                ("nfl", "Gridiron Giants", "Fantasy Football League"),
            ]
        )
        result = infer_sport("how are my Gridiron Giants doing", teams, None, None)
        assert result == "nfl"

    def test_league_name_in_message(self):
        teams = _teams_with_names(
            [
                ("nhl", "Team A", "Frozen Four League"),
                ("nfl", "Team B", "Touchdown League"),
            ]
        )
        result = infer_sport("what's happening in Touchdown League", teams, None, None)
        assert result == "nfl"

    def test_ambiguous_name_match_returns_none(self):
        teams = _teams_with_names(
            [
                ("nhl", "Winners", "League One"),
                ("nfl", "Winners", "League Two"),
            ]
        )
        result = infer_sport("how are the Winners doing", teams, None, None)
        assert result is None


class TestCarryForward:
    def test_stale_sport_used_when_no_signal(self):
        result = infer_sport(
            "should I make any moves",
            _teams("nhl", "nfl"),
            "nfl",
            _stale_timestamp(),
        )
        assert result == "nfl"

    def test_carry_forward_ignored_if_user_lost_that_sport(self):
        result = infer_sport(
            "should I make any moves",
            _teams("nhl", "nba"),
            "nfl",
            _stale_timestamp(),
        )
        assert result is None


class TestFallback:
    def test_no_signal_no_current_sport_returns_none(self):
        result = infer_sport("hello", _teams("nhl", "nfl"), None, None)
        assert result is None

    def test_empty_message(self):
        result = infer_sport("", _teams("nhl", "nfl"), None, None)
        assert result is None

    @pytest.mark.parametrize("teams", [[], None])
    def test_no_teams(self, teams):
        if teams is None:
            teams = []
        result = infer_sport("football", teams, None, None)
        assert result is None
