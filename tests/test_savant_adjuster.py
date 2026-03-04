"""Property-based tests for SavantAdjuster using Hypothesis.

Tests validate correctness properties from the design document (Properties 11–13).
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models.player import Player
from src.services.savant_adjuster import SavantAdjuster


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

HITTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF"]
PITCHER_POSITIONS = ["SP", "RP", "P"]


def hitter_strategy(obp=None):
    """Generate a hitter Player with a projected OBP."""
    return st.builds(
        Player,
        player_id=st.uuids().map(str),
        name=st.text(min_size=2, max_size=20),
        position=st.sampled_from(HITTER_POSITIONS),
        team=st.text(min_size=2, max_size=5),
        projected_obp=obp or st.floats(
            min_value=0.200, max_value=0.450,
            allow_nan=False, allow_infinity=False,
        ),
    )


def pitcher_strategy():
    """Generate a pitcher Player."""
    return st.builds(
        Player,
        player_id=st.uuids().map(str),
        name=st.text(min_size=2, max_size=20),
        position=st.sampled_from(PITCHER_POSITIONS),
        team=st.text(min_size=2, max_size=5),
        projected_era=st.floats(
            min_value=1.5, max_value=7.0,
            allow_nan=False, allow_infinity=False,
        ),
        projected_whip=st.floats(
            min_value=0.8, max_value=2.0,
            allow_nan=False, allow_infinity=False,
        ),
    )


def savant_strategy_with_xwoba(xwoba_range=None):
    """Generate a savant dict with xwoba and optional other metrics."""
    xwoba_st = xwoba_range or st.floats(
        min_value=0.200, max_value=0.450,
        allow_nan=False, allow_infinity=False,
    )
    return st.fixed_dictionaries({
        'xwoba': xwoba_st,
        'barrel_rate': st.floats(
            min_value=2.0, max_value=25.0,
            allow_nan=False, allow_infinity=False,
        ),
        'exit_velo': st.floats(
            min_value=82.0, max_value=100.0,
            allow_nan=False, allow_infinity=False,
        ),
        'sprint_speed': st.floats(
            min_value=22.0, max_value=32.0,
            allow_nan=False, allow_infinity=False,
        ),
    })


# ---------------------------------------------------------------------------
# Property 11: xwOBA adjustment direction
# Feature: recommendation-engine-rebuild, Property 11: xwOBA adjustment direction
# Validates: Requirements 5.1, 5.2, 5.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    obp=st.floats(min_value=0.200, max_value=0.450, allow_nan=False, allow_infinity=False),
    xwoba=st.floats(min_value=0.200, max_value=0.450, allow_nan=False, allow_infinity=False),
)
def test_xwoba_adjustment_direction(obp, xwoba):
    """For any hitter, the sign of the xwOBA-based adjustment matches the sign
    of (xwOBA - projected_obp) when the gap exceeds the threshold, and the
    total adjustment reflects that direction.

    **Validates: Requirements 5.1, 5.2, 5.3**
    """
    adjuster = SavantAdjuster()
    gap = xwoba - obp

    # Only test when gap clearly exceeds threshold
    assume(abs(gap) >= adjuster.XWOBA_GAP_THRESHOLD)

    player = Player(
        player_id="test_hitter",
        name="Test Hitter",
        position="OF",
        team="TST",
        projected_obp=obp,
    )
    # Savant dict with only xwoba (no power/speed metrics to isolate xwOBA effect)
    savant = {'xwoba': xwoba}

    adjustment, signal = adjuster.adjust(player, savant)

    if gap >= adjuster.XWOBA_GAP_THRESHOLD:
        # Buy-low: positive adjustment expected
        assert adjustment > 0, (
            f"Expected positive adjustment for buy-low gap={gap:.4f}, "
            f"xwoba={xwoba:.3f}, obp={obp:.3f}, got {adjustment}"
        )
        assert signal is not None and "Buy-low" in signal
    elif gap <= -adjuster.XWOBA_GAP_THRESHOLD:
        # Sell-high: negative adjustment expected
        assert adjustment < 0, (
            f"Expected negative adjustment for sell-high gap={gap:.4f}, "
            f"xwoba={xwoba:.3f}, obp={obp:.3f}, got {adjustment}"
        )
        assert signal is not None and "Sell-high" in signal



# ---------------------------------------------------------------------------
# Property 12: Above-average Savant metrics produce non-negative adjustments
# Feature: recommendation-engine-rebuild, Property 12: Above-average Savant metrics produce non-negative adjustments
# Validates: Requirements 5.4, 5.5
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    obp=st.floats(min_value=0.200, max_value=0.450, allow_nan=False, allow_infinity=False),
    barrel_rate=st.floats(min_value=8.1, max_value=25.0, allow_nan=False, allow_infinity=False),
    exit_velo=st.floats(min_value=88.6, max_value=100.0, allow_nan=False, allow_infinity=False),
    sprint_speed=st.floats(min_value=27.1, max_value=32.0, allow_nan=False, allow_infinity=False),
)
def test_above_average_savant_metrics_non_negative(obp, barrel_rate, exit_velo, sprint_speed):
    """For any hitter with above-average barrel rate + exit velo, the power
    adjustment component is non-negative. For above-average sprint speed,
    the speed adjustment component is non-negative. When the xwOBA gap is
    within threshold (no xwOBA adjustment), the total should be non-negative.

    **Validates: Requirements 5.4, 5.5**
    """
    adjuster = SavantAdjuster()

    # Set xwoba equal to obp so the gap is zero (within threshold) —
    # this isolates the power and speed components
    xwoba = obp

    player = Player(
        player_id="test_hitter",
        name="Test Hitter",
        position="1B",
        team="TST",
        projected_obp=obp,
    )
    savant = {
        'xwoba': xwoba,
        'barrel_rate': barrel_rate,
        'exit_velo': exit_velo,
        'sprint_speed': sprint_speed,
    }

    adjustment, _ = adjuster.adjust(player, savant)

    # With no xwOBA gap and above-average power + speed metrics,
    # the total adjustment should be non-negative
    assert adjustment >= 0.0, (
        f"Expected non-negative adjustment with above-avg metrics: "
        f"barrel_rate={barrel_rate}, exit_velo={exit_velo}, "
        f"sprint_speed={sprint_speed}, got {adjustment}"
    )


# ---------------------------------------------------------------------------
# Property 13: Pitcher Savant adjustment direction
# Feature: recommendation-engine-rebuild, Property 13: Pitcher Savant adjustment direction
# Validates: Requirement 5.6
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    xwoba=st.floats(min_value=0.200, max_value=0.314, allow_nan=False, allow_infinity=False),
)
def test_pitcher_savant_adjustment_direction(xwoba):
    """For any pitcher with xwOBA-against lower than league average (0.315),
    the adjustment should be positive (or zero), indicating the pitcher is
    effectively limiting contact quality.

    **Validates: Requirement 5.6**
    """
    adjuster = SavantAdjuster()

    # xwoba is strictly below AVG_XWOBA (0.315)
    assume(xwoba < adjuster.AVG_XWOBA)

    player = Player(
        player_id="test_pitcher",
        name="Test Pitcher",
        position="SP",
        team="TST",
        projected_era=3.50,
        projected_whip=1.20,
    )
    savant = {'xwoba': xwoba}

    adjustment, _ = adjuster.adjust(player, savant)

    assert adjustment > 0.0, (
        f"Expected positive adjustment for pitcher with xwOBA-against "
        f"{xwoba:.3f} < avg {adjuster.AVG_XWOBA}, got {adjustment}"
    )


# ---------------------------------------------------------------------------
# Unit tests for SavantAdjuster
# Validates: Requirements 5.1, 5.2, 5.3, 5.6, 5.7
# ---------------------------------------------------------------------------


class TestSavantAdjusterUnit:
    """Unit tests for specific SavantAdjuster scenarios."""

    def setup_method(self):
        self.adjuster = SavantAdjuster()

    def test_buy_low_candidate(self):
        """A hitter with high xwOBA but low actual OBP should get a positive
        adjustment and a 'Buy-low' signal.

        **Validates: Requirements 5.1, 5.2**
        """
        player = Player(
            player_id="buy_low_guy",
            name="Buy Low Guy",
            position="OF",
            team="TST",
            projected_obp=0.310,
        )
        savant = {
            'xwoba': 0.380,  # xwOBA well above projected OBP
            'barrel_rate': 12.0,
            'exit_velo': 91.0,
            'sprint_speed': 28.0,
        }

        adjustment, signal = self.adjuster.adjust(player, savant)

        assert adjustment > 0, f"Expected positive adjustment for buy-low, got {adjustment}"
        assert signal is not None
        assert "Buy-low" in signal

    def test_sell_high_candidate(self):
        """A hitter with low xwOBA but high actual OBP should get a negative
        adjustment and a 'Sell-high' signal.

        **Validates: Requirements 5.2, 5.3**
        """
        player = Player(
            player_id="sell_high_guy",
            name="Sell High Guy",
            position="1B",
            team="TST",
            projected_obp=0.380,
        )
        savant = {
            'xwoba': 0.300,  # xwOBA well below projected OBP
        }

        adjustment, signal = self.adjuster.adjust(player, savant)

        assert adjustment < 0, f"Expected negative adjustment for sell-high, got {adjustment}"
        assert signal is not None
        assert "Sell-high" in signal

    def test_no_savant_data_returns_zero(self):
        """A player with no savant data should get (0.0, None).

        **Validates: Requirement 5.7**
        """
        player = Player(
            player_id="no_savant",
            name="No Savant",
            position="SS",
            team="TST",
            projected_obp=0.350,
        )

        adjustment, signal = self.adjuster.adjust(player, None)

        assert adjustment == 0.0
        assert signal is None

    def test_pitcher_favorable_xwoba_against(self):
        """A pitcher with xwOBA-against below league average should get a
        positive adjustment.

        **Validates: Requirement 5.6**
        """
        player = Player(
            player_id="ace_pitcher",
            name="Ace Pitcher",
            position="SP",
            team="TST",
            projected_era=2.80,
            projected_whip=1.05,
        )
        savant = {
            'xwoba': 0.260,  # Well below AVG_XWOBA (0.315)
        }

        adjustment, signal = self.adjuster.adjust(player, savant)

        assert adjustment > 0, f"Expected positive adjustment for elite pitcher, got {adjustment}"
        assert signal is not None
        assert "Elite contact suppression" in signal
