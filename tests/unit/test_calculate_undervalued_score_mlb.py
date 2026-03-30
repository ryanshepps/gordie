from tools.mlb.player.calculate_undervalued_score_mlb import (
    BatterStats,
    PitcherStats,
    _calculate_batter_score,
    _calculate_pitcher_score,
)


def _batter(**overrides: str | int | float | None) -> BatterStats:
    defaults: dict[str, str | int | float | None] = {
        "player_name": "Test Batter",
        "team": "NYY",
        "position": "OF",
        "games_played": 100,
        "batting_avg": 0.270,
        "obp": 0.350,
        "slg": 0.450,
        "ops": 0.800,
        "woba": 0.340,
        "xwoba": 0.340,
        "barrel_pct": 7.0,
        "hard_hit_pct": 38.0,
        "k_pct": 22.0,
        "bb_pct": 9.0,
        "sprint_speed": None,
        "hr": 20,
        "rbi": 70,
        "sb": 5,
        "runs": 60,
    }
    return BatterStats.model_validate({**defaults, **overrides})


def _pitcher(**overrides: str | int | float | None) -> PitcherStats:
    defaults: dict[str, str | int | float | None] = {
        "player_name": "Test Pitcher",
        "team": "LAD",
        "position": "SP",
        "games_played": 25,
        "era": 3.50,
        "xera": 3.50,
        "fip": 3.40,
        "xfip": 3.40,
        "whip": 1.15,
        "k_pct": 22.0,
        "bb_pct": 7.5,
        "barrel_pct_against": 7.0,
        "hard_hit_pct_against": 35.0,
        "innings_pitched": 160.0,
        "wins": 10,
        "saves": 0,
    }
    return PitcherStats.model_validate({**defaults, **overrides})


class TestBatterScoring:
    def test_high_xwoba_gap_scores_high(self):
        stats = _batter(woba=0.300, xwoba=0.360)
        score, reasons = _calculate_batter_score(stats)
        assert score >= 4
        assert any("regression" in r.lower() for r in reasons)

    def test_moderate_xwoba_gap(self):
        stats = _batter(woba=0.330, xwoba=0.350)
        score, reasons = _calculate_batter_score(stats)
        assert score >= 2
        assert any("regression" in r.lower() for r in reasons)

    def test_overperforming_woba_penalized(self):
        stats = _batter(woba=0.380, xwoba=0.330)
        score, reasons = _calculate_batter_score(stats)
        assert score < 0
        assert any("overperforming" in r.lower() for r in reasons)

    def test_elite_barrel_pct_boosts_score(self):
        stats = _batter(barrel_pct=15.0)
        score, reasons = _calculate_batter_score(stats)
        assert score >= 3
        assert any("barrel" in r.lower() for r in reasons)

    def test_weak_barrel_pct_penalized(self):
        stats = _batter(barrel_pct=2.0)
        score, _ = _calculate_batter_score(stats)
        assert score <= -1

    def test_elite_hard_hit_boosts_score(self):
        stats = _batter(hard_hit_pct=48.0)
        score, _ = _calculate_batter_score(stats)
        assert score >= 2

    def test_high_strikeout_rate_penalized(self):
        stats = _batter(k_pct=35.0)
        _, reasons = _calculate_batter_score(stats)
        assert any("strikeout" in r.lower() for r in reasons)

    def test_low_strikeout_rate_rewarded(self):
        stats = _batter(k_pct=15.0)
        _, reasons = _calculate_batter_score(stats)
        assert any("bat-to-ball" in r.lower() for r in reasons)

    def test_sprint_speed_bonus(self):
        stats = _batter(sprint_speed=30.0)
        _, reasons = _calculate_batter_score(stats)
        assert any("sprint" in r.lower() or "stolen" in r.lower() for r in reasons)

    def test_no_sprint_speed_no_bonus(self):
        stats = _batter(sprint_speed=None)
        _, reasons = _calculate_batter_score(stats)
        assert not any("sprint" in r.lower() for r in reasons)

    def test_highly_undervalued_batter(self):
        stats = _batter(
            woba=0.290, xwoba=0.360, barrel_pct=14.0, hard_hit_pct=47.0,
            bb_pct=13.0, k_pct=16.0, sprint_speed=30.0,
        )
        score, _ = _calculate_batter_score(stats)
        assert score >= 10


class TestPitcherScoring:
    def test_high_era_xera_gap_scores_high(self):
        stats = _pitcher(era=5.00, xera=3.50)
        score, reasons = _calculate_pitcher_score(stats)
        assert score >= 4
        assert any("regression" in r.lower() for r in reasons)

    def test_moderate_era_gap(self):
        stats = _pitcher(era=4.00, xera=3.30)
        score, _ = _calculate_pitcher_score(stats)
        assert score >= 2

    def test_overperforming_era_penalized(self):
        stats = _pitcher(era=2.50, xera=4.00, k_pct=16.0, bb_pct=9.0, barrel_pct_against=8.0)
        score, reasons = _calculate_pitcher_score(stats)
        assert score < 0
        assert any("overperforming" in r.lower() for r in reasons)

    def test_elite_k_pct_boosts_score(self):
        stats = _pitcher(k_pct=30.0)
        score, reasons = _calculate_pitcher_score(stats)
        assert score >= 3
        assert any("strikeout" in r.lower() for r in reasons)

    def test_poor_control_penalized(self):
        stats = _pitcher(bb_pct=14.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("control" in r.lower() for r in reasons)

    def test_elite_control_rewarded(self):
        stats = _pitcher(bb_pct=5.0)
        score, _ = _calculate_pitcher_score(stats)
        assert score >= 2

    def test_low_barrel_against_rewarded(self):
        stats = _pitcher(barrel_pct_against=4.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("barrel" in r.lower() for r in reasons)

    def test_high_barrel_against_penalized(self):
        stats = _pitcher(barrel_pct_against=12.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("barrel" in r.lower() for r in reasons)

    def test_sp_durability_bonus(self):
        stats = _pitcher(position="SP", innings_pitched=180.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("durable" in r.lower() or "workload" in r.lower() for r in reasons)

    def test_sp_low_innings_concern(self):
        stats = _pitcher(position="SP", innings_pitched=80.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("workload" in r.lower() for r in reasons)

    def test_rp_no_innings_bonus_or_penalty(self):
        stats = _pitcher(position="RP", innings_pitched=50.0)
        _, reasons = _calculate_pitcher_score(stats)
        assert not any("workload" in r.lower() or "durable" in r.lower() for r in reasons)

    def test_fip_xfip_gap_bonus(self):
        stats = _pitcher(fip=4.00, xfip=3.30)
        _, reasons = _calculate_pitcher_score(stats)
        assert any("fip" in r.lower() for r in reasons)
