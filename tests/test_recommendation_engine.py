"""Property-based tests for RecommendationEngine composite scoring.

Tests validate correctness properties from the design document (Properties 24–27).
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import MagicMock, patch

from src.models.player import Player
from src.models.draft import DraftState, DraftPick
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HITTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF"]
PITCHER_POSITIONS = ["SP", "RP"]


def _make_hitter(pid, name="Hitter", position="OF", team="TST", **kwargs):
    """Create a hitter Player with sensible defaults."""
    defaults = dict(
        player_id=pid,
        name=name,
        position=position,
        team=team,
        projected_home_runs=25.0,
        projected_obp=0.340,
        projected_runs=80.0,
        projected_rbi=75.0,
        projected_stolen_bases=10.0,
        adp=50.0,
    )
    defaults.update(kwargs)
    return Player(**defaults)


def _make_pitcher(pid, name="Pitcher", position="SP", team="TST", **kwargs):
    """Create a pitcher Player with sensible defaults."""
    defaults = dict(
        player_id=pid,
        name=name,
        position=position,
        team=team,
        projected_wins=10.0,
        projected_quality_starts=15.0,
        projected_strikeouts=180.0,
        projected_era=3.50,
        projected_whip=1.20,
        projected_saves=0.0,
        projected_holds=0.0,
        projected_innings_pitched=180.0,
        adp=60.0,
    )
    defaults.update(kwargs)
    return Player(**defaults)


def _make_player_pool(n_hitters=15, n_pitchers=10):
    """Create a pool of players with varied stats for testing."""
    players = []
    positions = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "OF"]
    for i in range(n_hitters):
        pos = positions[i % len(positions)]
        players.append(_make_hitter(
            pid=f"hitter_{i}",
            name=f"Hitter {i}",
            position=pos,
            projected_home_runs=15.0 + i * 2,
            projected_obp=0.300 + i * 0.005,
            projected_runs=60.0 + i * 3,
            projected_rbi=55.0 + i * 3,
            projected_stolen_bases=5.0 + i,
            adp=float(10 + i * 5),
        ))
    for i in range(n_pitchers):
        pos = "SP" if i < 7 else "RP"
        players.append(_make_pitcher(
            pid=f"pitcher_{i}",
            name=f"Pitcher {i}",
            position=pos,
            projected_wins=8.0 + i,
            projected_quality_starts=10.0 + i,
            projected_strikeouts=120.0 + i * 10,
            projected_era=4.50 - i * 0.1,
            projected_whip=1.40 - i * 0.02,
            projected_saves=15.0 if pos == "RP" else 0.0,
            projected_holds=10.0 if pos == "RP" else 0.0,
            adp=float(20 + i * 6),
        ))
    return players


def _make_draft_state(current_pick=50, num_picks=0):
    """Create a DraftState for testing."""
    ds = DraftState(
        draft_id="test_draft",
        league_name="Test League",
        total_teams=13,
        roster_size=21,
        my_team_name="My Team",
        current_pick=current_pick,
        current_round=(current_pick - 1) // 13 + 1,
    )
    return ds


def _make_engine(players=None, savant_data=None, weights=None):
    """Create a RecommendationEngine with mocked dependencies."""
    if players is None:
        players = _make_player_pool()
    if savant_data is None:
        savant_data = {}

    mock_draft_service = MagicMock(spec=DraftService)
    mock_draft_service.current_draft = _make_draft_state()

    engine = RecommendationEngine(
        draft_service=mock_draft_service,
        players=players,
        savant_data=savant_data,
        weights=weights,
    )
    # Mock team_service.has_available_slot_for_player to always return True
    engine.team_service = MagicMock()
    engine.team_service.has_available_slot_for_player.return_value = True

    return engine


# ---------------------------------------------------------------------------
# Property 24: Composite score is weighted sum of components
# Feature: recommendation-engine-rebuild, Property 24: Composite score is weighted sum of components
# Validates: Requirements 12.1, 12.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    w_zscore=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_var=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_savant=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_scarcity=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_needs=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_relative=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_adp=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_pitcher_caps=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    w_balance=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_composite_score_is_weighted_sum(
    w_zscore, w_var, w_savant, w_scarcity, w_needs,
    w_relative, w_adp, w_pitcher_caps, w_balance,
):
    """For any set of weights, the final composite score returned by
    _score_player equals the weighted sum of the 9 individual component
    scores (zscore, VAR, savant, scarcity, needs, relative advantage,
    ADP value, pitcher caps, category balance).

    **Validates: Requirements 12.1, 12.2**
    """
    weights = {
        'zscore': w_zscore,
        'var': w_var,
        'savant': w_savant,
        'position_scarcity': w_scarcity,
        'team_needs': w_needs,
        'relative_advantage': w_relative,
        'adp_value': w_adp,
        'pitcher_caps': w_pitcher_caps,
        'category_balance': w_balance,
    }

    players = _make_player_pool(n_hitters=15, n_pitchers=10)
    engine = _make_engine(players=players, weights=weights)

    # Pick a player to score
    player = players[0]
    my_team = []
    available_players = players
    draft_state = _make_draft_state(current_pick=50)
    all_team_rosters = {}
    team_name = "My Team"

    # Compute z-scores and VAR
    zscores = engine.zscore_calc.calculate(available_players)
    var_scores = engine.replacement_analyzer.analyze(available_players, zscores)

    # Get the composite score from _score_player
    total_score, reasoning = engine._score_player(
        player, my_team, available_players, draft_state,
        all_team_rosters, zscores, var_scores, team_name,
    )

    # Now manually compute each component score and the expected weighted sum
    player_zscores = zscores.get(player.player_id, {})
    composite_z = player_zscores.get('composite', 0.0)

    var_value = var_scores.get(player.player_id, 0.0)

    savant_adj, _ = engine.savant_adjuster.adjust(
        player, engine.savant_data.get(player.player_id)
    )

    scarcity_score, _ = engine._score_position_scarcity(
        player, my_team, available_players, draft_state, all_team_rosters
    )

    needs_score, _ = engine._score_team_needs(
        player, my_team, draft_state, available_players
    )

    relative_score, _ = engine._score_relative_advantage(
        player, my_team, all_team_rosters, draft_state, team_name
    )

    adp_score, _ = engine._score_adp_value(player, draft_state)

    pitcher_cap_score, _ = engine._score_pitcher_caps(player, my_team, draft_state)

    balance_score, _ = engine._score_category_balance(
        player, my_team, all_team_rosters, team_name
    )

    expected = (
        composite_z * w_zscore
        + var_value * w_var
        + savant_adj * w_savant
        + max(min(scarcity_score / 12.5, 10.0), -5.0) * w_scarcity
        + max(min(needs_score / 60.0, 10.0), -10.0) * w_needs
        + max(min(relative_score / 8.0, 10.0), -5.0) * w_relative
        + max(min(adp_score / 20.0, 10.0), -10.0) * w_adp
        + max(min(pitcher_cap_score / 15.0, 5.0), -10.0) * w_pitcher_caps
        + max(min(balance_score / 30.0, 10.0), 0.0) * w_balance
    )

    assert abs(total_score - expected) < 1e-6, (
        f"Composite score {total_score} != expected weighted sum {expected}. "
        f"Components: z={composite_z}, var={var_value}, savant={savant_adj}, "
        f"scarcity={scarcity_score}, needs={needs_score}, relative={relative_score}, "
        f"adp={adp_score}, pitcher_caps={pitcher_cap_score}, balance={balance_score}"
    )


# ---------------------------------------------------------------------------
# Property 25: Recommendations sorted by descending score
# Feature: recommendation-engine-rebuild, Property 25: Recommendations sorted by descending score
# Validates: Requirement 12.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    top_n=st.integers(min_value=10, max_value=30),
)
def test_recommendations_sorted_by_descending_score(top_n):
    """For any list of recommendations returned by the engine, each
    recommendation's score is >= the next recommendation's score.

    **Validates: Requirement 12.4**
    """
    players = _make_player_pool(n_hitters=20, n_pitchers=15)
    engine = _make_engine(players=players)

    my_team = []
    draft_state = _make_draft_state(current_pick=30)

    recs = engine.get_recommendations(
        available_players=players,
        my_team=my_team,
        draft_state=draft_state,
        top_n=top_n,
    )

    # Verify descending order
    for i in range(len(recs) - 1):
        assert recs[i]['score'] >= recs[i + 1]['score'], (
            f"Recommendations not sorted at index {i}: "
            f"score[{i}]={recs[i]['score']:.4f} < score[{i+1}]={recs[i+1]['score']:.4f}"
        )


# ---------------------------------------------------------------------------
# Property 26: Recommendation count bounds
# Feature: recommendation-engine-rebuild, Property 26: Recommendation count bounds
# Validates: Requirement 12.5
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    n_hitters=st.integers(min_value=8, max_value=30),
    n_pitchers=st.integers(min_value=5, max_value=20),
    top_n=st.integers(min_value=10, max_value=30),
)
def test_recommendation_count_bounds(n_hitters, n_pitchers, top_n):
    """When 10+ available players exist, the engine returns between 10 and 30
    recommendations. When fewer than 10 are available, it returns all of them.

    **Validates: Requirement 12.5**
    """
    players = _make_player_pool(n_hitters=n_hitters, n_pitchers=n_pitchers)
    total_available = len(players)
    engine = _make_engine(players=players)

    my_team = []
    draft_state = _make_draft_state(current_pick=30)

    recs = engine.get_recommendations(
        available_players=players,
        my_team=my_team,
        draft_state=draft_state,
        top_n=top_n,
    )

    if total_available >= 10:
        assert 10 <= len(recs) <= 30, (
            f"Expected 10-30 recommendations with {total_available} available players, "
            f"got {len(recs)}"
        )
    else:
        # Fewer than 10 available — return all
        assert len(recs) <= total_available, (
            f"Expected at most {total_available} recommendations, got {len(recs)}"
        )


# ---------------------------------------------------------------------------
# Property 27: Savant signals appear in reasoning
# Feature: recommendation-engine-rebuild, Property 27: Savant signals appear in reasoning
# Validates: Requirements 12.3, 13.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    xwoba=st.floats(min_value=0.370, max_value=0.450, allow_nan=False, allow_infinity=False),
    obp=st.floats(min_value=0.250, max_value=0.320, allow_nan=False, allow_infinity=False),
)
def test_savant_signals_appear_in_reasoning(xwoba, obp):
    """When a player's Savant data triggers a buy-low signal (xwOBA exceeds
    actual OBP by more than the threshold), the reasoning string in the
    recommendation contains that signal text.

    **Validates: Requirements 12.3, 13.4**
    """
    from src.services.savant_adjuster import SavantAdjuster

    # Ensure the gap is large enough to trigger a buy-low signal
    assume(xwoba - obp >= SavantAdjuster.XWOBA_GAP_THRESHOLD)

    # Create a player pool where our target player is included
    target = _make_hitter(
        pid="buy_low_target",
        name="Buy Low Target",
        position="OF",
        projected_obp=obp,
        adp=10.0,  # High ADP so it's evaluated
    )
    # Build a pool with the target and enough other players
    other_players = _make_player_pool(n_hitters=15, n_pitchers=10)
    all_players = [target] + other_players

    savant_data = {
        "buy_low_target": {
            "xwoba": xwoba,
            "barrel_rate": 12.0,
            "exit_velo": 91.0,
            "sprint_speed": 28.0,
        }
    }

    engine = _make_engine(players=all_players, savant_data=savant_data)

    my_team = []
    draft_state = _make_draft_state(current_pick=30)

    recs = engine.get_recommendations(
        available_players=all_players,
        my_team=my_team,
        draft_state=draft_state,
        top_n=30,
    )

    # Find our target player in the recommendations
    target_recs = [r for r in recs if r['player'].player_id == "buy_low_target"]

    # The target should appear in recommendations (it has a good ADP)
    assert len(target_recs) > 0, (
        f"Expected buy_low_target in recommendations but not found. "
        f"Got {len(recs)} recs with player_ids: "
        f"{[r['player'].player_id for r in recs[:5]]}"
    )

    rec = target_recs[0]
    reasoning = rec['reasoning']

    # The reasoning should contain the buy-low signal
    assert "Buy-low" in reasoning, (
        f"Expected 'Buy-low' signal in reasoning for player with "
        f"xwOBA={xwoba:.3f} vs OBP={obp:.3f} (gap={xwoba - obp:.3f}). "
        f"Reasoning: {reasoning}"
    )


# ===========================================================================
# Integration Tests for Task 9.3
# Requirements: 12.1, 13.1
# ===========================================================================


class TestSmallDraftScenarioIntegration:
    """Integration test: 5 teams, 10 players — verify composite score matches
    manual calculation using the actual engine pipeline (ZScoreCalculator,
    ReplacementLevelAnalyzer, SavantAdjuster) with DEFAULT_WEIGHTS."""

    def _build_players(self):
        """Create 10 drafted players (2 per team) and 10 available players."""
        drafted = []
        teams = ["Team A", "Team B", "Team C", "Team D", "Team E"]
        # 2 hitters per team = 10 drafted
        for i, team in enumerate(teams):
            drafted.append(_make_hitter(
                pid=f"drafted_h_{i}", name=f"Drafted Hitter {i}",
                position=["C", "1B", "2B", "3B", "SS"][i], team=team,
                projected_home_runs=20.0 + i, projected_obp=0.320 + i * 0.005,
                projected_runs=70.0 + i, projected_rbi=65.0 + i,
                projected_stolen_bases=8.0 + i, adp=float(5 + i * 3),
            ))
            drafted.append(_make_pitcher(
                pid=f"drafted_p_{i}", name=f"Drafted Pitcher {i}",
                position="SP", team=team,
                projected_wins=9.0 + i, projected_quality_starts=12.0 + i,
                projected_strikeouts=150.0 + i * 10, projected_era=3.80 - i * 0.1,
                projected_whip=1.25 - i * 0.02, projected_saves=0.0,
                projected_holds=0.0, adp=float(10 + i * 4),
            ))

        available = []
        # 6 hitters + 4 pitchers available
        for i in range(6):
            pos = ["OF", "OF", "OF", "1B", "SS", "2B"][i]
            available.append(_make_hitter(
                pid=f"avail_h_{i}", name=f"Available Hitter {i}",
                position=pos,
                projected_home_runs=30.0 - i * 3,
                projected_obp=0.370 - i * 0.01,
                projected_runs=90.0 - i * 5,
                projected_rbi=85.0 - i * 4,
                projected_stolen_bases=15.0 - i,
                adp=float(20 + i * 8),
            ))
        for i in range(4):
            pos = "SP" if i < 3 else "RP"
            available.append(_make_pitcher(
                pid=f"avail_p_{i}", name=f"Available Pitcher {i}",
                position=pos,
                projected_wins=12.0 - i, projected_quality_starts=18.0 - i * 2,
                projected_strikeouts=200.0 - i * 15, projected_era=3.20 + i * 0.15,
                projected_whip=1.10 + i * 0.03, projected_saves=20.0 if pos == "RP" else 0.0,
                projected_holds=10.0 if pos == "RP" else 0.0,
                adp=float(15 + i * 7),
            ))
        return drafted, available

    def test_composite_score_matches_manual_calculation(self):
        """Verify the top recommendation's composite score equals the weighted
        sum of individually computed component scores.

        **Validates: Requirement 12.1**
        """
        from src.services.zscore_calculator import ZScoreCalculator
        from src.services.replacement_level import ReplacementLevelAnalyzer
        from src.services.savant_adjuster import SavantAdjuster

        drafted, available = self._build_players()
        all_players = drafted + available

        engine = _make_engine(players=all_players, savant_data={})
        weights = RecommendationEngine.DEFAULT_WEIGHTS

        my_team = []  # empty roster
        draft_state = _make_draft_state(current_pick=11, num_picks=10)

        recs = engine.get_recommendations(
            available_players=available,
            my_team=my_team,
            draft_state=draft_state,
            top_n=10,
        )

        assert len(recs) == 10, f"Expected 10 recommendations, got {len(recs)}"

        # Pick the top recommendation and manually verify its score
        top_rec = recs[0]
        player = top_rec['player']

        # Recompute each component independently
        zscore_calc = ZScoreCalculator()
        replacement_analyzer = ReplacementLevelAnalyzer()
        savant_adjuster = SavantAdjuster()

        zscores = zscore_calc.calculate(available)
        var_scores = replacement_analyzer.analyze(available, zscores)

        composite_z = zscores.get(player.player_id, {}).get('composite', 0.0)
        var_value = var_scores.get(player.player_id, 0.0)
        savant_adj, _ = savant_adjuster.adjust(player, None)

        scarcity_score, _ = engine._score_position_scarcity(
            player, my_team, available, draft_state, {}
        )
        needs_score, _ = engine._score_team_needs(
            player, my_team, draft_state, available
        )
        relative_score, _ = engine._score_relative_advantage(
            player, my_team, {}, draft_state, "My Team"
        )
        adp_score, _ = engine._score_adp_value(player, draft_state)
        pitcher_cap_score, _ = engine._score_pitcher_caps(player, my_team, draft_state)
        balance_score, _ = engine._score_category_balance(
            player, my_team, {}, "My Team"
        )

        expected_score = (
            composite_z * weights['zscore']
            + var_value * weights['var']
            + savant_adj * weights['savant']
            + max(min(scarcity_score / 12.5, 10.0), -5.0) * weights['position_scarcity']
            + max(min(needs_score / 60.0, 10.0), -10.0) * weights['team_needs']
            + max(min(relative_score / 8.0, 10.0), -5.0) * weights['relative_advantage']
            + max(min(adp_score / 20.0, 10.0), -10.0) * weights['adp_value']
            + max(min(pitcher_cap_score / 15.0, 5.0), -10.0) * weights['pitcher_caps']
            + max(min(balance_score / 30.0, 10.0), 0.0) * weights['category_balance']
        )

        assert abs(top_rec['score'] - expected_score) < 1e-4, (
            f"Top recommendation score {top_rec['score']:.6f} != "
            f"expected {expected_score:.6f}"
        )

    def test_recommendations_have_required_fields(self):
        """Each recommendation dict has 'player', 'score', 'reasoning' keys."""
        drafted, available = self._build_players()
        all_players = drafted + available

        engine = _make_engine(players=all_players, savant_data={})
        my_team = []
        draft_state = _make_draft_state(current_pick=11, num_picks=10)

        recs = engine.get_recommendations(
            available_players=available,
            my_team=my_team,
            draft_state=draft_state,
            top_n=10,
        )

        for rec in recs:
            assert 'player' in rec, "Missing 'player' key"
            assert 'score' in rec, "Missing 'score' key"
            assert 'reasoning' in rec, "Missing 'reasoning' key"
            assert isinstance(rec['score'], float), "score should be float"
            assert isinstance(rec['reasoning'], str), "reasoning should be str"
            assert isinstance(rec['player'], Player), "player should be Player"


class TestAPIEndpointIntegration:
    """Integration test: verify /api/recommendations returns the expected
    JSON shape with player, score, and reasoning fields.

    **Validates: Requirement 13.1**
    """

    def test_recommendations_endpoint_returns_expected_shape(self):
        """GET /api/recommendations after creating a draft returns a list of
        recommendations each with player (dict), score (float), reasoning (str)."""
        from src.api.app import app

        with app.test_client() as client:
            # 1. Create a draft
            create_resp = client.post('/api/draft/create', json={
                'draft_id': 'integration_test_draft',
                'league_name': 'Test League',
                'total_teams': 13,
                'roster_size': 21,
                'my_team_name': 'Runtime Terror',
            })
            assert create_resp.status_code == 200
            create_data = create_resp.get_json()
            assert create_data['success'] is True

            # 2. Get recommendations
            rec_resp = client.get('/api/recommendations')
            assert rec_resp.status_code == 200
            rec_data = rec_resp.get_json()

            # 3. Verify top-level shape
            assert 'recommendations' in rec_data, (
                f"Response missing 'recommendations' key. Keys: {list(rec_data.keys())}"
            )
            recs = rec_data['recommendations']
            assert isinstance(recs, list)
            assert len(recs) >= 1, "Expected at least 1 recommendation"

            # 4. Verify each recommendation's shape
            for i, rec in enumerate(recs):
                assert 'player' in rec, f"rec[{i}] missing 'player'"
                assert 'score' in rec, f"rec[{i}] missing 'score'"
                assert 'reasoning' in rec, f"rec[{i}] missing 'reasoning'"

                assert isinstance(rec['player'], dict), (
                    f"rec[{i}]['player'] should be dict, got {type(rec['player'])}"
                )
                assert isinstance(rec['score'], (int, float)), (
                    f"rec[{i}]['score'] should be numeric, got {type(rec['score'])}"
                )
                assert isinstance(rec['reasoning'], str), (
                    f"rec[{i}]['reasoning'] should be str, got {type(rec['reasoning'])}"
                )

                # Player dict should have key fields
                player = rec['player']
                assert 'player_id' in player, f"rec[{i}]['player'] missing 'player_id'"
                assert 'name' in player, f"rec[{i}]['player'] missing 'name'"
                assert 'position' in player, f"rec[{i}]['player'] missing 'position'"

    def test_recommendations_without_draft_returns_400(self):
        """GET /api/recommendations with no active draft returns 400."""
        from src.api.app import app, draft_service

        # Save and clear current draft
        saved_draft = draft_service.current_draft
        draft_service.current_draft = None

        try:
            with app.test_client() as client:
                resp = client.get('/api/recommendations')
                assert resp.status_code == 400
                data = resp.get_json()
                assert data['success'] is False
        finally:
            # Restore draft state
            draft_service.current_draft = saved_draft
