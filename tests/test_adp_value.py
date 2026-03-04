"""Unit tests for _score_adp_value in RecommendationEngine.

Validates requirements 9.1, 9.2, 9.3, 9.4.

Semantics:
  - Player still available past their ADP = value (fallen / steal)
  - Player picked before their ADP = reach
  - fallen = current_pick - ADP
    positive → value, negative → reach
"""
import pytest
from unittest.mock import MagicMock

from src.models.player import Player
from src.models.draft import DraftState, DraftPick
from src.services.recommendation_engine import RecommendationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(adp=None):
    """Create a minimal Player with the given ADP."""
    return Player(
        player_id="test_player",
        name="Test Player",
        position="OF",
        team="TST",
        adp=adp,
    )


def _make_draft_state(num_picks: int):
    """Create a DraftState with num_picks already made (current_pick = num_picks + 1)."""
    picks = [
        DraftPick(pick_number=i + 1, round=1, team_name="Team1", player_id=f"p{i}")
        for i in range(num_picks)
    ]
    return DraftState(
        draft_id="test",
        league_name="Test League",
        total_teams=13,
        roster_size=21,
        my_team_name="Team1",
        picks=picks,
    )


def _make_engine():
    """Create a minimal RecommendationEngine for testing _score_adp_value."""
    mock_draft_service = MagicMock()
    engine = RecommendationEngine(
        draft_service=mock_draft_service,
        players=[],
        savant_data={},
    )
    return engine


# ---------------------------------------------------------------------------
# Requirement 9.3: No ADP-based adjustment when ADP is None
# ---------------------------------------------------------------------------

class TestAdpNone:
    def test_none_adp_returns_zero(self):
        engine = _make_engine()
        player = _make_player(adp=None)
        ds = _make_draft_state(num_picks=50)

        score, reason = engine._score_adp_value(player, ds)

        assert score == 0.0
        assert "No ADP data" in reason

    def test_none_adp_early_draft(self):
        engine = _make_engine()
        player = _make_player(adp=None)
        ds = _make_draft_state(num_picks=0)  # pick 1

        score, reason = engine._score_adp_value(player, ds)

        assert score == 0.0

    def test_none_adp_late_draft(self):
        engine = _make_engine()
        player = _make_player(adp=None)
        ds = _make_draft_state(num_picks=200)

        score, reason = engine._score_adp_value(player, ds)

        assert score == 0.0


# ---------------------------------------------------------------------------
# Requirement 9.1: Positive value when player has fallen past ADP
# (current_pick > ADP → player is a steal)
# ---------------------------------------------------------------------------

class TestAdpValue:
    def test_value_pick_positive_score(self):
        """Player with ADP 40 still available at pick 50 → fallen 10 → positive."""
        engine = _make_engine()
        player = _make_player(adp=40.0)
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        score, reason = engine._score_adp_value(player, ds)

        assert score > 0
        assert "value" in reason.lower() or "steal" in reason.lower()

    def test_value_scales_with_gap(self):
        """Larger fall → larger value score."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        small_fall = _make_player(adp=45.0)  # fallen 5 picks
        big_fall = _make_player(adp=30.0)    # fallen 20 picks

        small_score, _ = engine._score_adp_value(small_fall, ds)
        big_score, _ = engine._score_adp_value(big_fall, ds)

        assert big_score > small_score > 0

    def test_exact_adp_match_returns_zero(self):
        """ADP exactly equals current pick → 0 score."""
        engine = _make_engine()
        player = _make_player(adp=50.0)
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        score, reason = engine._score_adp_value(player, ds)

        assert score == 0.0
        assert "at adp" in reason.lower()

    def test_big_steal_label(self):
        """Player fallen 20+ picks gets 'steal' label."""
        engine = _make_engine()
        player = _make_player(adp=15.0)
        ds = _make_draft_state(num_picks=64)  # current_pick = 65, fallen 50

        score, reason = engine._score_adp_value(player, ds)

        assert score > 0
        assert "steal" in reason.lower()


# ---------------------------------------------------------------------------
# Requirement 9.2: Negative reach when picking before ADP
# (current_pick < ADP → reaching for the player)
# ---------------------------------------------------------------------------

class TestAdpReach:
    def test_reach_negative_score(self):
        """Player with ADP 60 at pick 50 → reaching 10 picks early → negative."""
        engine = _make_engine()
        player = _make_player(adp=60.0)
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        score, reason = engine._score_adp_value(player, ds)

        assert score < 0
        assert "reach" in reason.lower() or "available later" in reason.lower()

    def test_reach_magnitude_increases_with_gap(self):
        """Larger reach → more negative score."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        small_reach = _make_player(adp=52.0)  # 2 picks early
        big_reach = _make_player(adp=65.0)    # 15 picks early

        small_score, _ = engine._score_adp_value(small_reach, ds)
        big_score, _ = engine._score_adp_value(big_reach, ds)

        assert small_score < 0
        assert big_score < 0
        assert big_score < small_score  # more negative


# ---------------------------------------------------------------------------
# Requirement 9.4: Tiered reach penalties
# ---------------------------------------------------------------------------

class TestTieredReach:
    def test_small_reach_1_to_3(self):
        """1-3 picks early → -1 per pick."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        p1 = _make_player(adp=51.0)  # 1 pick early
        p2 = _make_player(adp=52.0)  # 2 picks early
        p3 = _make_player(adp=53.0)  # 3 picks early

        s1, r1 = engine._score_adp_value(p1, ds)
        s2, r2 = engine._score_adp_value(p2, ds)
        s3, r3 = engine._score_adp_value(p3, ds)

        assert s1 == pytest.approx(-1.0)
        assert s2 == pytest.approx(-2.0)
        assert s3 == pytest.approx(-3.0)
        assert "small reach" in r1
        assert "small reach" in r3

    def test_moderate_reach_4_to_9(self):
        """4-9 picks early → first 3 at -1, rest at -2."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        p4 = _make_player(adp=54.0)  # 4 picks early
        p9 = _make_player(adp=59.0)  # 9 picks early

        s4, r4 = engine._score_adp_value(p4, ds)
        s9, r9 = engine._score_adp_value(p9, ds)

        # 4 picks: -3 (first 3) + -2 (1 extra) = -5
        assert s4 == pytest.approx(-5.0)
        # 9 picks: -3 (first 3) + -12 (6 extra at -2) = -15
        assert s9 == pytest.approx(-15.0)
        assert "moderate reach" in r4
        assert "moderate reach" in r9

    def test_large_reach_10_plus(self):
        """10+ picks early → first 3 at -1, next 6 at -2, rest at -3."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)  # current_pick = 50

        p10 = _make_player(adp=60.0)  # 10 picks early
        p15 = _make_player(adp=65.0)  # 15 picks early

        s10, r10 = engine._score_adp_value(p10, ds)
        s15, r15 = engine._score_adp_value(p15, ds)

        # 10 picks: -3 + -12 + -3 = -18
        assert s10 == pytest.approx(-18.0)
        # 15 picks: -3 + -12 + -18 = -33
        assert s15 == pytest.approx(-33.0)
        assert "large reach" in r10
        assert "large reach" in r15

    def test_tiered_penalties_increase_across_tiers(self):
        """Penalty per-pick is steeper in higher tiers."""
        engine = _make_engine()
        ds = _make_draft_state(num_picks=49)

        s3, _ = engine._score_adp_value(_make_player(adp=53.0), ds)   # 3 early
        s4, _ = engine._score_adp_value(_make_player(adp=54.0), ds)   # 4 early
        s9, _ = engine._score_adp_value(_make_player(adp=59.0), ds)   # 9 early
        s10, _ = engine._score_adp_value(_make_player(adp=60.0), ds)  # 10 early

        marginal_3_to_4 = abs(s4 - s3)   # crossing into moderate tier
        marginal_9_to_10 = abs(s10 - s9)  # crossing into large tier

        assert marginal_3_to_4 == pytest.approx(2.0)
        assert marginal_9_to_10 == pytest.approx(3.0)
