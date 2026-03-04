"""Property-based tests for ZScoreCalculator using Hypothesis.

Tests validate correctness properties from the design document (Properties 5–7).
"""
import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models.player import Player
from src.services.zscore_calculator import ZScoreCalculator


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

HITTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF"]
PITCHER_POSITIONS = ["SP", "RP", "P"]


def hitter_strategy():
    """Generate a hitter Player with valid batting projections."""
    return st.builds(
        Player,
        player_id=st.uuids().map(str),
        name=st.text(min_size=2, max_size=20),
        position=st.sampled_from(HITTER_POSITIONS),
        team=st.text(min_size=2, max_size=5),
        projected_home_runs=st.floats(min_value=0, max_value=60, allow_nan=False, allow_infinity=False),
        projected_obp=st.floats(min_value=0.150, max_value=0.500, allow_nan=False, allow_infinity=False),
        projected_runs=st.floats(min_value=0, max_value=150, allow_nan=False, allow_infinity=False),
        projected_rbi=st.floats(min_value=0, max_value=160, allow_nan=False, allow_infinity=False),
        projected_stolen_bases=st.floats(min_value=0, max_value=80, allow_nan=False, allow_infinity=False),
    )


def pitcher_strategy():
    """Generate a pitcher Player with valid pitching projections."""
    return st.builds(
        Player,
        player_id=st.uuids().map(str),
        name=st.text(min_size=2, max_size=20),
        position=st.sampled_from(PITCHER_POSITIONS),
        team=st.text(min_size=2, max_size=5),
        projected_wins=st.floats(min_value=0, max_value=25, allow_nan=False, allow_infinity=False),
        projected_quality_starts=st.floats(min_value=0, max_value=30, allow_nan=False, allow_infinity=False),
        projected_strikeouts=st.floats(min_value=0, max_value=350, allow_nan=False, allow_infinity=False),
        projected_era=st.floats(min_value=1.0, max_value=8.0, allow_nan=False, allow_infinity=False),
        projected_whip=st.floats(min_value=0.7, max_value=2.0, allow_nan=False, allow_infinity=False),
        projected_saves=st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False),
        projected_holds=st.floats(min_value=0, max_value=35, allow_nan=False, allow_infinity=False),
        projected_innings_pitched=st.floats(min_value=0, max_value=250, allow_nan=False, allow_infinity=False),
    )


# ---------------------------------------------------------------------------
# Property 5: Z-score formula correctness
# Feature: recommendation-engine-rebuild, Property 5: Z-score formula correctness
# Validates: Requirements 3.1, 3.3, 3.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(hitters=st.lists(hitter_strategy(), min_size=3, max_size=15))
def test_zscore_formula_correctness(hitters):
    """For any pool of hitters, each z-score equals (value - mean) / std
    and composite equals the sum of category z-scores.

    **Validates: Requirements 3.1, 3.3, 3.4**
    """
    # Ensure unique player IDs
    seen_ids = set()
    unique_hitters = []
    for h in hitters:
        if h.player_id not in seen_ids:
            seen_ids.add(h.player_id)
            unique_hitters.append(h)
    assume(len(unique_hitters) >= 3)
    hitters = unique_hitters

    calc = ZScoreCalculator()
    result = calc.calculate(hitters)

    # Manually compute mean and population stddev per batting category
    for cat in ZScoreCalculator.BATTING_CATEGORIES:
        values = []
        for p in hitters:
            v = calc._player_category_value(p, cat)
            if v is not None:
                values.append((p.player_id, v))

        if len(values) < 2:
            continue

        raw_vals = [v for _, v in values]
        mean = sum(raw_vals) / len(raw_vals)
        variance = sum((x - mean) ** 2 for x in raw_vals) / len(raw_vals)
        std = math.sqrt(variance)

        if std < 1e-9:
            # All z-scores should be 0.0
            for pid, _ in values:
                assert result[pid][cat] == pytest.approx(0.0, abs=1e-9)
        else:
            inverted = cat in ZScoreCalculator.INVERTED_CATEGORIES
            for pid, val in values:
                if inverted:
                    expected_z = (mean - val) / std
                else:
                    expected_z = (val - mean) / std
                assert result[pid][cat] == pytest.approx(expected_z, abs=1e-9), (
                    f"Z-score mismatch for player {pid}, category {cat}"
                )

    # Verify composite = sum of category z-scores
    for p in hitters:
        if p.player_id in result:
            scores = result[p.player_id]
            cat_sum = sum(scores[cat] for cat in ZScoreCalculator.BATTING_CATEGORIES)
            assert scores['composite'] == pytest.approx(cat_sum, abs=1e-9), (
                f"Composite mismatch for player {p.player_id}"
            )


# ---------------------------------------------------------------------------
# Property 6: Inverted z-scores for rate categories
# Feature: recommendation-engine-rebuild, Property 6: Inverted z-scores for rate categories
# Validates: Requirement 3.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    pitcher_a=pitcher_strategy(),
    pitcher_b=pitcher_strategy(),
    others=st.lists(pitcher_strategy(), min_size=1, max_size=10),
)
def test_inverted_zscores_for_rate_categories(pitcher_a, pitcher_b, others):
    """For any two pitchers where A has lower ERA than B, A's ERA z-score
    should be higher. Same for WHIP.

    **Validates: Requirement 3.2**
    """
    # Ensure unique player IDs across all pitchers
    pitcher_a = Player(**{**pitcher_a.__dict__, 'player_id': 'pitcher_a'})
    pitcher_b = Player(**{**pitcher_b.__dict__, 'player_id': 'pitcher_b'})
    for i, p in enumerate(others):
        others[i] = Player(**{**p.__dict__, 'player_id': f'other_{i}'})

    all_pitchers = [pitcher_a, pitcher_b] + others

    # Ensure both pitchers have distinct ERA and WHIP values
    assume(pitcher_a.projected_era is not None and pitcher_b.projected_era is not None)
    assume(pitcher_a.projected_whip is not None and pitcher_b.projected_whip is not None)
    assume(abs(pitcher_a.projected_era - pitcher_b.projected_era) > 1e-6)
    assume(abs(pitcher_a.projected_whip - pitcher_b.projected_whip) > 1e-6)

    calc = ZScoreCalculator()
    result = calc.calculate(all_pitchers)

    # ERA: lower is better, so lower ERA → higher z-score
    if pitcher_a.projected_era < pitcher_b.projected_era:
        assert result['pitcher_a']['ERA'] >= result['pitcher_b']['ERA'], (
            f"Lower ERA ({pitcher_a.projected_era}) should yield higher z-score "
            f"than higher ERA ({pitcher_b.projected_era})"
        )
    else:
        assert result['pitcher_b']['ERA'] >= result['pitcher_a']['ERA']

    # WHIP: lower is better, so lower WHIP → higher z-score
    if pitcher_a.projected_whip < pitcher_b.projected_whip:
        assert result['pitcher_a']['WHIP'] >= result['pitcher_b']['WHIP'], (
            f"Lower WHIP ({pitcher_a.projected_whip}) should yield higher z-score "
            f"than higher WHIP ({pitcher_b.projected_whip})"
        )
    else:
        assert result['pitcher_b']['WHIP'] >= result['pitcher_a']['WHIP']


# ---------------------------------------------------------------------------
# Property 7: Derived category formulas
# Feature: recommendation-engine-rebuild, Property 7: Derived category formulas
# Validates: Requirements 3.6, 3.7
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(pitcher=pitcher_strategy())
def test_derived_category_formulas(pitcher):
    """For any pitcher with saves, holds, wins, and quality_starts,
    SHOLDS = saves + holds×0.5 and WQS = wins + quality_starts.

    **Validates: Requirements 3.6, 3.7**
    """
    assume(pitcher.projected_saves is not None)
    assume(pitcher.projected_holds is not None)
    assume(pitcher.projected_wins is not None)
    assume(pitcher.projected_quality_starts is not None)

    calc = ZScoreCalculator()

    # Verify SHOLDS formula
    sholds = calc._player_category_value(pitcher, 'SHOLDS')
    expected_sholds = pitcher.projected_saves + (pitcher.projected_holds * 0.5)
    assert sholds == pytest.approx(expected_sholds, abs=1e-9), (
        f"SHOLDS should be {expected_sholds}, got {sholds}"
    )

    # Verify WQS formula
    wqs = calc._player_category_value(pitcher, 'WQS')
    expected_wqs = pitcher.projected_wins + pitcher.projected_quality_starts
    assert wqs == pytest.approx(expected_wqs, abs=1e-9), (
        f"WQS should be {expected_wqs}, got {wqs}"
    )


# ===========================================================================
# Unit tests for ZScoreCalculator
# ===========================================================================


class TestZScoreHandComputed:
    """Hand-computed z-score example with 3 hitters.

    Players: HR values 10, 20, 30
    mean = (10 + 20 + 30) / 3 = 20
    population variance = ((10-20)^2 + (20-20)^2 + (30-20)^2) / 3
                        = (100 + 0 + 100) / 3 = 200/3
    population std = sqrt(200/3) ≈ 8.16496580927726

    Expected z-scores:
      player1 HR z = (10 - 20) / 8.165 ≈ -1.2247
      player2 HR z = (20 - 20) / 8.165 =  0.0
      player3 HR z = (30 - 20) / 8.165 ≈  1.2247

    Validates: Requirements 3.1, 3.2
    """

    def _make_hitters(self):
        return [
            Player(player_id="h1", name="Hitter One", position="OF", team="NYY",
                   projected_home_runs=10.0, projected_obp=0.300,
                   projected_runs=60.0, projected_rbi=50.0, projected_stolen_bases=5.0),
            Player(player_id="h2", name="Hitter Two", position="1B", team="BOS",
                   projected_home_runs=20.0, projected_obp=0.300,
                   projected_runs=60.0, projected_rbi=50.0, projected_stolen_bases=5.0),
            Player(player_id="h3", name="Hitter Three", position="3B", team="LAD",
                   projected_home_runs=30.0, projected_obp=0.300,
                   projected_runs=60.0, projected_rbi=50.0, projected_stolen_bases=5.0),
        ]

    def test_hand_computed_hr_zscores(self):
        hitters = self._make_hitters()
        calc = ZScoreCalculator()
        result = calc.calculate(hitters)

        std = math.sqrt(200.0 / 3.0)  # ≈ 8.16496580927726

        assert result["h1"]["HR"] == pytest.approx(-10.0 / std, abs=1e-6)
        assert result["h2"]["HR"] == pytest.approx(0.0, abs=1e-6)
        assert result["h3"]["HR"] == pytest.approx(10.0 / std, abs=1e-6)

    def test_hand_computed_composite_equals_sum(self):
        """Composite should equal the sum of all 5 batting category z-scores."""
        hitters = self._make_hitters()
        calc = ZScoreCalculator()
        result = calc.calculate(hitters)

        for pid in ["h1", "h2", "h3"]:
            cat_sum = sum(result[pid][cat] for cat in ZScoreCalculator.BATTING_CATEGORIES)
            assert result[pid]["composite"] == pytest.approx(cat_sum, abs=1e-9)

    def test_identical_categories_yield_zero_zscores(self):
        """When OBP, R, RBI, SB are identical across players, those z-scores are 0."""
        hitters = self._make_hitters()
        calc = ZScoreCalculator()
        result = calc.calculate(hitters)

        # OBP, R, RBI, SB are all identical → std=0 → z=0.0
        for pid in ["h1", "h2", "h3"]:
            for cat in ["OBP", "R", "RBI", "SB"]:
                assert result[pid][cat] == pytest.approx(0.0, abs=1e-9)


class TestZeroStddev:
    """Verify that zero standard deviation returns 0.0 z-scores.

    Validates: Requirement 3.5
    """

    def test_zscore_method_returns_zero_on_zero_std(self):
        calc = ZScoreCalculator()
        assert calc._zscore(value=42.0, mean=30.0, std=0.0, inverted=False) == 0.0
        assert calc._zscore(value=42.0, mean=30.0, std=0.0, inverted=True) == 0.0

    def test_all_same_values_produce_zero_zscores(self):
        """If every player has the same HR, all HR z-scores should be 0.0."""
        players = [
            Player(player_id="a", name="A", position="OF", team="T",
                   projected_home_runs=25.0, projected_obp=0.350,
                   projected_runs=80.0, projected_rbi=90.0, projected_stolen_bases=10.0),
            Player(player_id="b", name="B", position="1B", team="T",
                   projected_home_runs=25.0, projected_obp=0.350,
                   projected_runs=80.0, projected_rbi=90.0, projected_stolen_bases=10.0),
            Player(player_id="c", name="C", position="2B", team="T",
                   projected_home_runs=25.0, projected_obp=0.350,
                   projected_runs=80.0, projected_rbi=90.0, projected_stolen_bases=10.0),
        ]
        calc = ZScoreCalculator()
        result = calc.calculate(players)

        for pid in ["a", "b", "c"]:
            for cat in ZScoreCalculator.BATTING_CATEGORIES:
                assert result[pid][cat] == pytest.approx(0.0, abs=1e-9)
            assert result[pid]["composite"] == pytest.approx(0.0, abs=1e-9)


class TestSHOLDSAndWQS:
    """Verify SHOLDS and WQS derived category formulas with known values.

    SHOLDS = projected_saves + (projected_holds × 0.5)
    WQS = projected_wins + projected_quality_starts

    Validates: Requirements 3.6, 3.7
    """

    def test_sholds_formula(self):
        calc = ZScoreCalculator()
        pitcher = Player(player_id="p1", name="Pitcher", position="SP", team="T",
                         projected_saves=20.0, projected_holds=10.0,
                         projected_wins=12.0, projected_quality_starts=18.0,
                         projected_strikeouts=200.0, projected_era=3.50, projected_whip=1.20)
        # SHOLDS = 20 + (10 * 0.5) = 25.0
        assert calc._player_category_value(pitcher, "SHOLDS") == pytest.approx(25.0)

    def test_wqs_formula(self):
        calc = ZScoreCalculator()
        pitcher = Player(player_id="p1", name="Pitcher", position="SP", team="T",
                         projected_saves=5.0, projected_holds=8.0,
                         projected_wins=15.0, projected_quality_starts=20.0,
                         projected_strikeouts=180.0, projected_era=3.80, projected_whip=1.25)
        # WQS = 15 + 20 = 35.0
        assert calc._player_category_value(pitcher, "WQS") == pytest.approx(35.0)

    def test_sholds_none_when_missing_holds(self):
        calc = ZScoreCalculator()
        pitcher = Player(player_id="p1", name="Pitcher", position="SP", team="T",
                         projected_saves=20.0, projected_holds=None)
        assert calc._player_category_value(pitcher, "SHOLDS") is None

    def test_wqs_none_when_missing_quality_starts(self):
        calc = ZScoreCalculator()
        pitcher = Player(player_id="p1", name="Pitcher", position="SP", team="T",
                         projected_wins=10.0, projected_quality_starts=None)
        assert calc._player_category_value(pitcher, "WQS") is None


class TestERAWHIPInversion:
    """Verify ERA and WHIP inversion: lower values → higher z-scores.

    Validates: Requirement 3.2
    """

    def test_lower_era_yields_higher_zscore(self):
        pitchers = [
            Player(player_id="ace", name="Ace", position="SP", team="T",
                   projected_era=2.50, projected_whip=1.00, projected_strikeouts=220.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=15.0, projected_quality_starts=25.0),
            Player(player_id="mid", name="Mid", position="SP", team="T",
                   projected_era=4.00, projected_whip=1.25, projected_strikeouts=180.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=10.0, projected_quality_starts=15.0),
            Player(player_id="bad", name="Bad", position="SP", team="T",
                   projected_era=5.50, projected_whip=1.50, projected_strikeouts=140.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=5.0, projected_quality_starts=8.0),
        ]
        calc = ZScoreCalculator()
        result = calc.calculate(pitchers)

        # Ace (ERA 2.50) should have the highest ERA z-score
        assert result["ace"]["ERA"] > result["mid"]["ERA"]
        assert result["mid"]["ERA"] > result["bad"]["ERA"]

    def test_lower_whip_yields_higher_zscore(self):
        pitchers = [
            Player(player_id="ace", name="Ace", position="SP", team="T",
                   projected_era=3.00, projected_whip=0.90, projected_strikeouts=200.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=12.0, projected_quality_starts=20.0),
            Player(player_id="mid", name="Mid", position="SP", team="T",
                   projected_era=3.00, projected_whip=1.20, projected_strikeouts=200.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=12.0, projected_quality_starts=20.0),
            Player(player_id="bad", name="Bad", position="SP", team="T",
                   projected_era=3.00, projected_whip=1.50, projected_strikeouts=200.0,
                   projected_saves=0.0, projected_holds=0.0,
                   projected_wins=12.0, projected_quality_starts=20.0),
        ]
        calc = ZScoreCalculator()
        result = calc.calculate(pitchers)

        # Ace (WHIP 0.90) should have the highest WHIP z-score
        assert result["ace"]["WHIP"] > result["mid"]["WHIP"]
        assert result["mid"]["WHIP"] > result["bad"]["WHIP"]

    def test_inversion_sign_is_correct(self):
        """Directly verify the _zscore method inverts correctly."""
        calc = ZScoreCalculator()
        # Normal: (value - mean) / std = (2 - 5) / 1 = -3.0
        assert calc._zscore(2.0, 5.0, 1.0, inverted=False) == pytest.approx(-3.0)
        # Inverted: (mean - value) / std = (5 - 2) / 1 = 3.0
        assert calc._zscore(2.0, 5.0, 1.0, inverted=True) == pytest.approx(3.0)
