from agent.news.lineup_analyzer import (
    LineupAnalysis,
    RosterPositionConfig,
    analyze_lineup,
    parse_roster_position_configs,
)
from agent.news.news_digest import (
    InjuryAlert,
    MatchupAlert,
    RawNewsCollection,
    RosterPlayer,
)
from agent.news.news_processor import process_news_for_user


class FakePlayer:
    def __init__(self, name: str, team: str, slot: str, position: str):
        self.name = type("Name", (), {"full": name})()
        self.editorial_team_abbr = team
        self.selected_position_value = slot
        self.display_position = position


def _make_roster_player(
    name: str,
    nhl_team: str = "EDM",
    roster_slot: str = "C",
    position: str = "C",
) -> RosterPlayer:
    return RosterPlayer(name=name, nhl_team=nhl_team, roster_slot=roster_slot, position=position)


def _standard_roster_configs() -> list[RosterPositionConfig]:
    return [
        RosterPositionConfig(position="C", count=2, is_starting_position=True),
        RosterPositionConfig(position="LW", count=2, is_starting_position=True),
        RosterPositionConfig(position="RW", count=2, is_starting_position=True),
        RosterPositionConfig(position="D", count=4, is_starting_position=True),
        RosterPositionConfig(position="G", count=2, is_starting_position=True),
        RosterPositionConfig(position="Util", count=1, is_starting_position=True),
        RosterPositionConfig(position="BN", count=3, is_starting_position=False),
        RosterPositionConfig(position="IR", count=2, is_starting_position=False),
    ]


def _digest_kwargs(**overrides):
    defaults = {
        "user_email": "test@example.com",
        "league_id": "123",
        "team_id": "1",
        "league_name": "Test League",
        "team_name": "Test Team",
    }
    return {**defaults, **overrides}


class TestLineupAnalyzer:
    def test_no_decisions_when_all_players_fit(self):
        roster = [
            _make_roster_player("connor mcdavid", "EDM", "C"),
            _make_roster_player("leon draisaitl", "EDM", "C"),
        ]

        result = analyze_lineup(roster, {"EDM"}, _standard_roster_configs())

        assert not result.has_lineup_decisions
        assert result.benched_players_with_games == []
        assert result.position_conflicts == {}

    def test_bench_reminder_when_player_has_game_and_slot_open(self):
        roster = [
            _make_roster_player("connor mcdavid", "EDM", "C"),
            _make_roster_player("leon draisaitl", "EDM", "BN"),
        ]

        result = analyze_lineup(roster, {"EDM"}, _standard_roster_configs())

        assert "leon draisaitl" in result.benched_players_with_games

    def test_no_bench_reminder_for_ir_slot_players(self):
        roster = [
            _make_roster_player("connor mcdavid", "EDM", "C"),
            _make_roster_player("injured player", "EDM", "IR"),
        ]

        result = analyze_lineup(roster, {"EDM"}, _standard_roster_configs())

        assert "injured player" not in result.benched_players_with_games

    def test_position_conflict_when_more_players_than_slots_plus_util(self):
        roster = [
            _make_roster_player("player1", "EDM", "C"),
            _make_roster_player("player2", "EDM", "C"),
            _make_roster_player("player3", "EDM", "BN"),
            _make_roster_player("player4", "EDM", "BN"),
        ]

        result = analyze_lineup(roster, {"EDM"}, _standard_roster_configs())

        assert "C" in result.position_conflicts
        assert len(result.position_conflicts["C"]) == 4

    def test_no_decisions_when_no_games_today(self):
        roster = [
            _make_roster_player("connor mcdavid", "EDM", "C"),
            _make_roster_player("leon draisaitl", "EDM", "BN"),
        ]

        result = analyze_lineup(roster, {"TOR"}, _standard_roster_configs())

        assert not result.has_lineup_decisions


class TestInjuryGameDayFiltering:
    def test_new_injury_surfaces_without_game_today(self):
        raw_news = RawNewsCollection(
            injuries=[
                InjuryAlert(player_name="Connor McDavid", team="EDM", status="DTD", description="Upper body")
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today=set(),
            previous_injury_states={},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.injury_alerts) == 1
        assert digest.injury_alerts[0].is_new_injury
        assert not digest.injury_alerts[0].has_game_today

    def test_repeat_injury_without_game_today_is_suppressed(self):
        raw_news = RawNewsCollection(
            injuries=[
                InjuryAlert(player_name="Connor McDavid", team="EDM", status="DTD", description="Upper body")
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today=set(),
            previous_injury_states={"connor mcdavid": "DTD"},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.injury_alerts) == 0

    def test_repeat_injury_with_game_today_surfaces(self):
        raw_news = RawNewsCollection(
            injuries=[
                InjuryAlert(player_name="Connor McDavid", team="EDM", status="DTD", description="Upper body")
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"EDM"},
            previous_injury_states={"connor mcdavid": "DTD"},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.injury_alerts) == 1
        assert digest.injury_alerts[0].has_game_today

    def test_status_change_treated_as_new(self):
        raw_news = RawNewsCollection(
            injuries=[
                InjuryAlert(player_name="Connor McDavid", team="EDM", status="OUT", description="Upper body")
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today=set(),
            previous_injury_states={"connor mcdavid": "DTD"},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.injury_alerts) == 1
        assert digest.injury_alerts[0].is_new_injury

    def test_ir_slot_player_gets_no_replacement_language(self):
        raw_news = RawNewsCollection(
            injuries=[
                InjuryAlert(player_name="Mikko Rantanen", team="COL", status="IR", description="Knee")
            ],
        )
        roster = [FakePlayer("Mikko Rantanen", "COL", "IR", "RW")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"COL"},
            previous_injury_states={},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.injury_alerts) == 1
        assert digest.injury_alerts[0].already_on_ir_slot
        assert "No roster action needed" in digest.injury_alerts[0].fantasy_impact


class TestMatchupGameDayFiltering:
    def test_matchup_alerts_suppressed_when_no_lineup_decisions(self):
        raw_news = RawNewsCollection(
            matchups=[
                MatchupAlert(player_name="Connor McDavid", opponent="TOR", opponent_goals_against_avg=3.5)
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]
        lineup = LineupAnalysis(has_lineup_decisions=False, position_conflicts={})

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"EDM"},
            previous_injury_states={},
            lineup_analysis=lineup,
            **_digest_kwargs(),
        )

        assert len(digest.matchup_alerts) == 0

    def test_matchup_alerts_included_when_position_conflicts_exist(self):
        raw_news = RawNewsCollection(
            matchups=[
                MatchupAlert(player_name="Connor McDavid", opponent="TOR", opponent_goals_against_avg=3.5)
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]
        lineup = LineupAnalysis(
            has_lineup_decisions=True,
            position_conflicts={"C": ["connor mcdavid", "leon draisaitl", "player3", "player4"]},
        )

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"EDM"},
            previous_injury_states={},
            lineup_analysis=lineup,
            **_digest_kwargs(),
        )

        assert len(digest.matchup_alerts) == 1

    def test_matchup_alerts_included_when_no_lineup_analysis_provided(self):
        raw_news = RawNewsCollection(
            matchups=[
                MatchupAlert(player_name="Connor McDavid", opponent="TOR", opponent_goals_against_avg=3.5)
            ],
        )
        roster = [FakePlayer("Connor McDavid", "EDM", "C", "C")]

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"EDM"},
            previous_injury_states={},
            lineup_analysis=None,
            **_digest_kwargs(),
        )

        assert len(digest.matchup_alerts) == 1


class TestBenchRemindersInDigest:
    def test_bench_reminders_populated_from_lineup_analysis(self):
        raw_news = RawNewsCollection()
        roster = [FakePlayer("Connor McDavid", "EDM", "BN", "C")]
        lineup = LineupAnalysis(
            has_lineup_decisions=True,
            benched_players_with_games=["connor mcdavid"],
        )

        digest = process_news_for_user(
            raw_news=raw_news,
            roster=roster,
            teams_playing_today={"EDM"},
            previous_injury_states={},
            lineup_analysis=lineup,
            **_digest_kwargs(),
        )

        assert "connor mcdavid" in digest.bench_reminders
        assert digest.has_alerts()


class TestParseRosterPositionConfigs:
    def test_parses_standard_format(self):
        settings_json = '{"roster_positions": [{"position": "C", "count": 2, "is_starting_position": true}, {"position": "BN", "count": 3, "is_starting_position": false}]}'

        result = parse_roster_position_configs(settings_json)

        assert len(result) == 2
        assert result[0].position == "C"
        assert result[0].count == 2
        assert result[0].is_starting_position

    def test_parses_wrapped_format(self):
        settings_json = '{"roster_positions": {"roster_position": [{"position": "C", "count": 2, "is_starting_position": true}]}}'

        result = parse_roster_position_configs(settings_json)

        assert len(result) == 1

    def test_returns_empty_for_invalid_json(self):
        assert parse_roster_position_configs("not json") == []

    def test_returns_empty_for_missing_roster_positions(self):
        assert parse_roster_position_configs('{"other_key": "value"}') == []
