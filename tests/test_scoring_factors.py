"""Property-based tests for scoring factors in RecommendationEngine.

Tests validate correctness properties from the design document (Property 14).
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import MagicMock

from src.models.player import Player
from src.models.draft import DraftState
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HITTER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF"]
FLEX_POSITIONS = ["MI", "CI", "U"]


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


def _make_draft_state(current_pick=50):
    """Create a DraftState for testing."""
    return DraftState(
        draft_id="test_draft",
        league_name="Test League",
        total_teams=13,
        roster_size=21,
        my_team_name="My Team",
        current_pick=current_pick,
        current_round=(current_pick - 1) // 13 + 1,
    )


def _make_engine(players=None, savant_data=None, weights=None):
    """Create a RecommendationEngine with mocked dependencies."""
    if players is None:
        players = []
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
    return engine


# ---------------------------------------------------------------------------
# Property 14: Position scarcity monotonicity
# Feature: recommendation-engine-rebuild, Property 14: Position scarcity monotonicity
#
# As the ratio of above-average remaining players to teams needing that
# position decreases, the scarcity score for players at that position should
# increase (or stay the same). Flex positions should use the combined
# eligible player pool.
#
# **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
# ---------------------------------------------------------------------------


@given(
    position=st.sampled_from(HITTER_POSITIONS),
    fewer_above_avg=st.integers(min_value=0, max_value=10),
    extra_above_avg=st.integers(min_value=1, max_value=15),
    teams_needing=st.integers(min_value=1, max_value=13),
    below_avg_count=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_scarcity_monotonicity_fewer_above_avg_means_higher_score(
    position, fewer_above_avg, extra_above_avg, teams_needing, below_avg_count
):
    """Property 14: With fewer above-average players at a position (relative to
    teams needing), the scarcity score should be >= the score with more
    above-average players.

    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    engine = _make_engine()
    draft_state = _make_draft_state()

    # The player being scored
    target = _make_hitter("target", position=position, adp=50.0)

    # My team is empty (not relevant for scarcity, but required param)
    my_team = []

    # Build "fewer" scenario: fewer_above_avg above-avg players at position
    fewer_pool = [target]
    for i in range(fewer_above_avg):
        fewer_pool.append(
            _make_hitter(f"above_{i}", position=position, adp=float(50 + i))
        )
    # Add below-avg players (adp=None → not above-avg)
    for i in range(below_avg_count):
        fewer_pool.append(
            _make_hitter(f"below_{i}", position=position, adp=None)
        )

    # Build "more" scenario: fewer_above_avg + extra above-avg players
    more_pool = list(fewer_pool)  # copy the fewer pool
    for i in range(extra_above_avg):
        more_pool.append(
            _make_hitter(f"extra_{i}", position=position, adp=float(100 + i))
        )

    # Build team rosters where exactly teams_needing teams need this position
    all_team_rosters = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing:
            # Team needs the position (empty roster)
            all_team_rosters[team_name] = []
        else:
            # Team already has the position filled
            all_team_rosters[team_name] = [
                _make_hitter(f"filled_{t}", position=position)
            ]

    score_fewer, _ = engine._score_position_scarcity(
        target, my_team, fewer_pool, draft_state, all_team_rosters
    )
    score_more, _ = engine._score_position_scarcity(
        target, my_team, more_pool, draft_state, all_team_rosters
    )

    assert score_fewer >= score_more, (
        f"Scarcity should be >= with fewer above-avg players. "
        f"Position={position}, fewer_above_avg={fewer_above_avg}, "
        f"more_above_avg={fewer_above_avg + extra_above_avg}, "
        f"teams_needing={teams_needing}, "
        f"score_fewer={score_fewer}, score_more={score_more}"
    )


@given(
    teams_needing_fewer=st.integers(min_value=1, max_value=6),
    extra_teams=st.integers(min_value=1, max_value=7),
    above_avg_count=st.integers(min_value=1, max_value=10),
    position=st.sampled_from(HITTER_POSITIONS),
)
@settings(max_examples=100)
def test_scarcity_monotonicity_more_teams_needing_means_higher_score(
    teams_needing_fewer, extra_teams, above_avg_count, position
):
    """Property 14: With more teams needing a position (same above-avg supply),
    the scarcity score should be >= the score with fewer teams needing.

    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    teams_needing_more = teams_needing_fewer + extra_teams
    assume(teams_needing_more <= 13)

    engine = _make_engine()
    draft_state = _make_draft_state()
    target = _make_hitter("target", position=position, adp=50.0)
    my_team = []

    # Same available pool for both scenarios
    pool = [target]
    for i in range(above_avg_count):
        pool.append(
            _make_hitter(f"above_{i}", position=position, adp=float(50 + i))
        )

    # Fewer teams needing
    rosters_fewer_need = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing_fewer:
            rosters_fewer_need[team_name] = []
        else:
            rosters_fewer_need[team_name] = [
                _make_hitter(f"filled_{t}", position=position)
            ]

    # More teams needing
    rosters_more_need = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing_more:
            rosters_more_need[team_name] = []
        else:
            rosters_more_need[team_name] = [
                _make_hitter(f"filled_{t}", position=position)
            ]

    score_more_need, _ = engine._score_position_scarcity(
        target, my_team, pool, draft_state, rosters_more_need
    )
    score_fewer_need, _ = engine._score_position_scarcity(
        target, my_team, pool, draft_state, rosters_fewer_need
    )

    assert score_more_need >= score_fewer_need, (
        f"Scarcity should be >= with more teams needing. "
        f"Position={position}, teams_fewer={teams_needing_fewer}, "
        f"teams_more={teams_needing_more}, above_avg={above_avg_count}, "
        f"score_more_need={score_more_need}, score_fewer_need={score_fewer_need}"
    )


@settings(max_examples=100)
@given(
    above_avg_count=st.integers(min_value=0, max_value=10),
    teams_needing=st.integers(min_value=1, max_value=13),
)
def test_catcher_scarcity_bonus(above_avg_count, teams_needing):
    """Catcher inherent scarcity bonus: C always gets +25 over the same
    scenario at a non-catcher position.

    **Validates: Requirements 6.1, 6.4**
    """
    engine = _make_engine()
    draft_state = _make_draft_state()
    my_team = []

    catcher = _make_hitter("target_c", position="C", adp=50.0)
    first_baseman = _make_hitter("target_1b", position="1B", adp=50.0)

    # Build identical pools for each position
    c_pool = [catcher]
    fb_pool = [first_baseman]
    for i in range(above_avg_count):
        c_pool.append(_make_hitter(f"c_{i}", position="C", adp=float(50 + i)))
        fb_pool.append(_make_hitter(f"fb_{i}", position="1B", adp=float(50 + i)))

    # Same team rosters structure for both
    rosters_c = {}
    rosters_fb = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing:
            rosters_c[team_name] = []
            rosters_fb[team_name] = []
        else:
            rosters_c[team_name] = [_make_hitter(f"fc_{t}", position="C")]
            rosters_fb[team_name] = [_make_hitter(f"ffb_{t}", position="1B")]

    score_c, reason_c = engine._score_position_scarcity(
        catcher, my_team, c_pool, draft_state, rosters_c
    )
    score_fb, _ = engine._score_position_scarcity(
        first_baseman, my_team, fb_pool, draft_state, rosters_fb
    )

    assert score_c == score_fb + 25.0, (
        f"Catcher should get exactly +25 bonus. "
        f"score_C={score_c}, score_1B={score_fb}, diff={score_c - score_fb}"
    )
    assert "(C scarce)" in reason_c


@given(
    flex_pos=st.sampled_from(["MI", "CI"]),
    above_avg_per_sub=st.integers(min_value=1, max_value=8),
    teams_needing=st.integers(min_value=1, max_value=13),
)
@settings(max_examples=100)
def test_flex_positions_use_combined_pool(flex_pos, above_avg_per_sub, teams_needing):
    """Property 14 (flex): Flex positions (MI, CI) use the combined eligible
    player pool for scarcity calculation.

    MI draws from 2B + SS; CI draws from 1B + 3B.

    **Validates: Requirements 6.5**
    """
    FLEX_ELIGIBLE = {
        "MI": ["2B", "SS"],
        "CI": ["1B", "3B"],
    }
    sub_positions = FLEX_ELIGIBLE[flex_pos]

    engine = _make_engine()
    draft_state = _make_draft_state()
    my_team = []

    # Target player at the flex position
    target = _make_hitter("target", position=flex_pos, adp=50.0)

    # Build pool with above-avg players from both sub-positions
    pool = [target]
    for sub_pos in sub_positions:
        for i in range(above_avg_per_sub):
            pool.append(
                _make_hitter(
                    f"{sub_pos}_{i}", position=sub_pos, adp=float(50 + i)
                )
            )

    # Build team rosters
    all_team_rosters = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing:
            all_team_rosters[team_name] = []
        else:
            # Fill with a player from one of the sub-positions
            all_team_rosters[team_name] = [
                _make_hitter(f"filled_{t}", position=sub_positions[0])
            ]

    score, reasoning = engine._score_position_scarcity(
        target, my_team, pool, draft_state, all_team_rosters
    )

    # The combined pool should have above_avg_per_sub * 2 above-avg players
    # (plus the target itself which also has adp=50 < 300)
    total_above_avg = above_avg_per_sub * len(sub_positions) + 1  # +1 for target
    expected_ratio = total_above_avg / teams_needing

    # Verify the score matches the expected tier for the combined ratio
    if expected_ratio < 0.5:
        assert score == 80.0
    elif expected_ratio < 1.0:
        assert score == 60.0
    elif expected_ratio < 2.0:
        assert score == 35.0
    else:
        assert score == 15.0


@settings(max_examples=100)
@given(teams_needing=st.integers(min_value=1, max_value=13))
def test_no_above_avg_left_gives_max_scarcity(teams_needing):
    """When no above-average players remain at a position, scarcity should
    be at maximum (100.0, or 125.0 for catcher).

    **Validates: Requirements 6.1, 6.2**
    """
    engine = _make_engine()
    draft_state = _make_draft_state()
    my_team = []

    # Target has no ADP (not above-avg) and pool has only below-avg players
    target = _make_hitter("target", position="SS", adp=None)
    pool = [target]
    for i in range(5):
        pool.append(_make_hitter(f"below_{i}", position="SS", adp=None))

    all_team_rosters = {}
    for t in range(13):
        team_name = f"Team_{t}"
        if t < teams_needing:
            all_team_rosters[team_name] = []
        else:
            all_team_rosters[team_name] = [
                _make_hitter(f"filled_{t}", position="SS")
            ]

    score, reasoning = engine._score_position_scarcity(
        target, my_team, pool, draft_state, all_team_rosters
    )

    assert score == 100.0, f"Expected 100.0 for no above-avg left, got {score}"
    assert "no above-avg left" in reasoning


@settings(max_examples=100)
@given(position=st.sampled_from(HITTER_POSITIONS))
def test_all_teams_filled_gives_min_scarcity(position):
    """When all teams have filled the position, scarcity should be minimal (5.0,
    or 30.0 for catcher due to +25 bonus).

    **Validates: Requirements 6.1, 6.3**
    """
    engine = _make_engine()
    draft_state = _make_draft_state()
    my_team = []

    target = _make_hitter("target", position=position, adp=50.0)
    pool = [target]

    # All 13 teams have the position filled
    # OF requires 4 slots, P requires 9, all others require 1
    position_requirements = {
        'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
        'MI': 1, 'CI': 1, 'OF': 4, 'U': 1, 'P': 9, 'SP': 9, 'RP': 9,
    }
    required = position_requirements.get(position, 1)
    all_team_rosters = {}
    for t in range(13):
        all_team_rosters[f"Team_{t}"] = [
            _make_hitter(f"filled_{t}_{s}", position=position)
            for s in range(required)
        ]

    score, _ = engine._score_position_scarcity(
        target, my_team, pool, draft_state, all_team_rosters
    )

    expected = 30.0 if position == "C" else 5.0
    assert score == expected, (
        f"Expected {expected} for all-teams-filled at {position}, got {score}"
    )


# ---------------------------------------------------------------------------
# Property 15: Unfilled position needs bonus
# Feature: recommendation-engine-rebuild, Property 15: Unfilled position needs bonus
#
# For any team with an unfilled required roster position and a player eligible
# for that position, the team needs score should be positive.
#
# **Validates: Requirement 7.2**
# ---------------------------------------------------------------------------


@given(
    position=st.sampled_from(["C", "1B", "2B", "3B", "SS", "OF"]),
    current_pick=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=100)
def test_unfilled_position_needs_bonus(position, current_pick):
    """Property 15: When a team has an unfilled required position and the player
    is eligible for that position, the team needs score should be positive.

    **Validates: Requirement 7.2**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=current_pick)

    # Player eligible for the unfilled position
    player = _make_hitter("target", position=position, adp=50.0)

    # Empty team — all positions unfilled
    my_team = []

    available = [player] + [
        _make_hitter(f"filler_{i}", position="OF") for i in range(10)
    ]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    assert score > 0, (
        f"Unfilled position {position} should yield positive needs score, "
        f"got {score}. Reasoning: {reasoning}"
    )


@given(
    position=st.sampled_from(["C", "1B", "2B", "3B", "SS"]),
    other_players_count=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_unfilled_primary_slot_gives_bonus_even_with_some_roster(
    position, other_players_count
):
    """Property 15: Even with some roster filled, an unfilled primary position
    still yields a positive needs score for an eligible player.

    **Validates: Requirement 7.2**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    player = _make_hitter("target", position=position, adp=50.0)

    # Build a team that does NOT have the target position filled
    # Use OF players so they don't fill the target position
    my_team = [
        _make_hitter(f"of_{i}", position="OF") for i in range(other_players_count)
    ]

    available = [player] + [
        _make_hitter(f"filler_{i}", position="OF") for i in range(10)
    ]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    assert score > 0, (
        f"Unfilled {position} with {other_players_count} other players should "
        f"yield positive needs score, got {score}. Reasoning: {reasoning}"
    )


# ---------------------------------------------------------------------------
# Property 16: Filled position negative adjustment
# Feature: recommendation-engine-rebuild, Property 16: Filled position negative adjustment
#
# For any team that has reached the maximum player count at a position, the
# team needs score for an additional player at that position should be negative.
#
# **Validates: Requirement 7.3**
# ---------------------------------------------------------------------------


@given(
    position=st.sampled_from(["C", "1B", "2B", "3B", "SS"]),
)
@settings(max_examples=100)
def test_maxed_position_negative_adjustment(position):
    """Property 16: When a team has the maximum number of players at a position,
    the needs score for an additional player at that position should be negative.

    **Validates: Requirement 7.3**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    # Player at the position we want to test
    player = _make_hitter("target", position=position, adp=50.0)

    # Build a full roster that has the position maxed (1 slot each for C/1B/2B/3B/SS)
    # Fill all hitter slots so the "hitters_needed" doesn't add positive score
    my_team = [
        _make_hitter("c_1", position="C"),
        _make_hitter("1b_1", position="1B"),
        _make_hitter("2b_1", position="2B"),
        _make_hitter("3b_1", position="3B"),
        _make_hitter("ss_1", position="SS"),
        _make_hitter("2b_2", position="2B"),   # fills MI
        _make_hitter("1b_2", position="1B"),   # fills CI
        _make_hitter("of_1", position="OF"),
        _make_hitter("of_2", position="OF"),
        _make_hitter("of_3", position="OF"),
        _make_hitter("of_4", position="OF"),
        _make_hitter("of_5", position="OF"),   # fills U (12th hitter > 11 slots)
    ]

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    assert score < 0, (
        f"Maxed position {position} should yield negative needs score, "
        f"got {score}. Reasoning: {reasoning}"
    )


@given(
    extra_pitchers=st.integers(min_value=0, max_value=3),
)
@settings(max_examples=100)
def test_maxed_pitcher_slots_negative_adjustment(extra_pitchers):
    """Property 16: When a team has 9+ pitchers, adding another pitcher should
    yield a negative needs score.

    **Validates: Requirement 7.3**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    player = _make_pitcher("target_p", adp=60.0)

    # Team with 9 + extra pitchers (maxed)
    my_team = [
        _make_pitcher(f"sp_{i}") for i in range(9 + extra_pitchers)
    ]

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    assert score < 0, (
        f"Team with {9 + extra_pitchers} pitchers should yield negative needs "
        f"score for another pitcher, got {score}. Reasoning: {reasoning}"
    )


# ---------------------------------------------------------------------------
# Property 17: Flex position eligibility in needs scoring
# Feature: recommendation-engine-rebuild, Property 17: Flex position eligibility in needs
#
# For any team with an unfilled MI slot and a player whose primary position is
# 2B or SS, the needs scoring should recognize that player as filling the MI
# need (and similarly for CI with 1B/3B, and U with any hitter).
#
# **Validates: Requirement 7.4**
# ---------------------------------------------------------------------------


@given(
    mi_position=st.sampled_from(["2B", "SS"]),
)
@settings(max_examples=100)
def test_flex_mi_eligibility(mi_position):
    """Property 17: A 2B or SS player should get a bonus for filling an unfilled
    MI slot.

    **Validates: Requirement 7.4**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    player = _make_hitter("target", position=mi_position, adp=50.0)

    # Team has the primary 2B and SS slots filled, but MI is unfilled
    # Use one 2B and one SS to fill primary slots only
    my_team = [
        _make_hitter("2b_1", position="2B"),
        _make_hitter("ss_1", position="SS"),
    ]

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    # The player should get a MI flex bonus
    assert "MI" in reasoning, (
        f"Player at {mi_position} should be recognized as filling MI need. "
        f"Reasoning: {reasoning}"
    )
    assert score > 0, (
        f"Player at {mi_position} filling MI should have positive score, "
        f"got {score}. Reasoning: {reasoning}"
    )


@given(
    ci_position=st.sampled_from(["1B", "3B"]),
)
@settings(max_examples=100)
def test_flex_ci_eligibility(ci_position):
    """Property 17: A 1B or 3B player should get a bonus for filling an unfilled
    CI slot.

    **Validates: Requirement 7.4**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    player = _make_hitter("target", position=ci_position, adp=50.0)

    # Team has the primary 1B and 3B slots filled, but CI is unfilled
    my_team = [
        _make_hitter("1b_1", position="1B"),
        _make_hitter("3b_1", position="3B"),
    ]

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    # The player should get a CI flex bonus
    assert "CI" in reasoning, (
        f"Player at {ci_position} should be recognized as filling CI need. "
        f"Reasoning: {reasoning}"
    )
    assert score > 0, (
        f"Player at {ci_position} filling CI should have positive score, "
        f"got {score}. Reasoning: {reasoning}"
    )


@given(
    hitter_position=st.sampled_from(["C", "1B", "2B", "3B", "SS", "OF"]),
)
@settings(max_examples=100)
def test_flex_u_eligibility(hitter_position):
    """Property 17: Any hitter should get a bonus for filling an unfilled U slot.

    **Validates: Requirement 7.4**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    player = _make_hitter("target", position=hitter_position, adp=50.0)

    # Empty team — U slot is unfilled
    my_team = []

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    # The player should get a U flex bonus
    assert "U" in reasoning, (
        f"Hitter at {hitter_position} should be recognized as filling U need. "
        f"Reasoning: {reasoning}"
    )


# ---------------------------------------------------------------------------
# Property 18: Pitcher baseline needs
# Feature: recommendation-engine-rebuild, Property 18: Pitcher baseline needs
#
# For any team with fewer than 9 pitchers, the team needs score for any pitcher
# should be non-negative.
#
# **Validates: Requirement 7.5**
# ---------------------------------------------------------------------------


@given(
    pitcher_count=st.integers(min_value=0, max_value=8),
    pitcher_type=st.sampled_from(["SP", "RP"]),
    current_pick=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=100)
def test_pitcher_baseline_needs(pitcher_count, pitcher_type, current_pick):
    """Property 18: When a team has fewer than 9 pitchers, the needs score for
    any pitcher should be non-negative.

    **Validates: Requirement 7.5**
    """
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=current_pick)

    player = _make_pitcher("target_p", position=pitcher_type, adp=60.0)

    # Team with pitcher_count pitchers (all below 9)
    my_team = [
        _make_pitcher(f"sp_{i}") for i in range(pitcher_count)
    ]

    available = [player]

    score, reasoning = engine._score_team_needs(player, my_team, draft_state, available)

    assert score >= 0, (
        f"Team with {pitcher_count} pitchers (< 9) should yield non-negative "
        f"needs score for a pitcher, got {score}. Reasoning: {reasoning}"
    )


# ---------------------------------------------------------------------------
# Property 19: Relative advantage scales with category ranking
# Feature: recommendation-engine-rebuild, Property 19: Relative advantage scales with ranking
#
# For any team and scoring category, the bonus applied for a player improving
# that category should be larger when the team ranks in the bottom third
# (9th–13th) than when the team ranks in the top third (1st–4th).
#
# **Validates: Requirements 8.2, 8.3**
# ---------------------------------------------------------------------------


def _build_rosters_for_rank(team_name, category, target_rank, num_teams=13):
    """Build all_team_rosters so that `team_name` has a specific rank in `category`.

    For counting stats (higher is better): rank 1 = highest value.
    For rate stats (ERA, WHIP): rank 1 = lowest value.

    Returns (all_team_rosters, my_team) where my_team is the roster for team_name.
    """
    from src.services.standings_calculator import StandingsCalculator

    LOWER_IS_BETTER = {'ERA', 'WHIP'}
    lower_better = category in LOWER_IS_BETTER

    all_team_rosters = {}

    # Batting categories: HR, OBP, R, RBI, SB
    # Pitching categories: ERA, K, SHOLDS, WHIP, WQS
    # We need to create rosters that produce specific category totals.

    for t in range(num_teams):
        tname = f"Team_{t}" if t > 0 else team_name
        # Assign a rank-based value: rank 1 should be best
        # For higher-is-better: rank 1 gets highest value
        # For lower-is-better: rank 1 gets lowest value
        if t == 0:
            rank = target_rank
        else:
            # Distribute other teams across remaining ranks
            # Skip the target_rank position
            available_ranks = [r for r in range(1, num_teams + 1) if r != target_rank]
            rank = available_ranks[t - 1]

        if category in ('HR', 'R', 'RBI', 'SB'):
            # Counting stat: higher is better, rank 1 = highest
            val = float((num_teams - rank + 1) * 10)
            if category == 'HR':
                roster = [_make_hitter(f"h_{tname}", position="OF",
                                       projected_home_runs=val, projected_obp=0.300,
                                       projected_runs=50.0, projected_rbi=50.0,
                                       projected_stolen_bases=5.0)]
            elif category == 'R':
                roster = [_make_hitter(f"h_{tname}", position="OF",
                                       projected_home_runs=10.0, projected_obp=0.300,
                                       projected_runs=val, projected_rbi=50.0,
                                       projected_stolen_bases=5.0)]
            elif category == 'RBI':
                roster = [_make_hitter(f"h_{tname}", position="OF",
                                       projected_home_runs=10.0, projected_obp=0.300,
                                       projected_runs=50.0, projected_rbi=val,
                                       projected_stolen_bases=5.0)]
            else:  # SB
                roster = [_make_hitter(f"h_{tname}", position="OF",
                                       projected_home_runs=10.0, projected_obp=0.300,
                                       projected_runs=50.0, projected_rbi=50.0,
                                       projected_stolen_bases=val)]
        elif category == 'OBP':
            # Rate stat but higher is better
            val = 0.250 + (num_teams - rank + 1) * 0.010
            roster = [_make_hitter(f"h_{tname}", position="OF",
                                   projected_home_runs=10.0, projected_obp=val,
                                   projected_runs=50.0, projected_rbi=50.0,
                                   projected_stolen_bases=5.0)]
        elif category == 'K':
            val = float((num_teams - rank + 1) * 20)
            roster = [_make_pitcher(f"p_{tname}", projected_strikeouts=val,
                                    projected_era=3.50, projected_whip=1.20,
                                    projected_wins=5.0, projected_quality_starts=5.0,
                                    projected_saves=0.0, projected_holds=0.0)]
        elif category == 'WQS':
            val = float((num_teams - rank + 1) * 3)
            roster = [_make_pitcher(f"p_{tname}", projected_strikeouts=100.0,
                                    projected_era=3.50, projected_whip=1.20,
                                    projected_wins=val / 2, projected_quality_starts=val / 2,
                                    projected_saves=0.0, projected_holds=0.0)]
        elif category == 'SHOLDS':
            val = float((num_teams - rank + 1) * 5)
            roster = [_make_pitcher(f"p_{tname}", projected_strikeouts=100.0,
                                    projected_era=3.50, projected_whip=1.20,
                                    projected_wins=5.0, projected_quality_starts=5.0,
                                    projected_saves=val, projected_holds=0.0)]
        elif category == 'ERA':
            # Lower is better: rank 1 = lowest ERA
            val = 2.50 + (rank - 1) * 0.30
            roster = [_make_pitcher(f"p_{tname}", projected_strikeouts=100.0,
                                    projected_era=val, projected_whip=1.20,
                                    projected_wins=5.0, projected_quality_starts=5.0,
                                    projected_saves=0.0, projected_holds=0.0)]
        elif category == 'WHIP':
            # Lower is better: rank 1 = lowest WHIP
            val = 1.00 + (rank - 1) * 0.05
            roster = [_make_pitcher(f"p_{tname}", projected_strikeouts=100.0,
                                    projected_era=3.50, projected_whip=val,
                                    projected_wins=5.0, projected_quality_starts=5.0,
                                    projected_saves=0.0, projected_holds=0.0)]
        else:
            roster = []

        all_team_rosters[tname] = roster

    my_team = all_team_rosters[team_name]
    return all_team_rosters, my_team


@given(
    category=st.sampled_from(['HR', 'OBP', 'R', 'RBI', 'SB',
                              'ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']),
    bottom_rank=st.integers(min_value=9, max_value=13),
    top_rank=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=100)
def test_relative_advantage_bottom_third_bonus_exceeds_top_third(
    category, bottom_rank, top_rank
):
    """Property 19: The bonus for improving a category should be larger when
    the team ranks in the bottom third (9th-13th) than when the team ranks
    in the top third (1st-4th).

    **Validates: Requirements 8.2, 8.3**
    """
    team_name = "My Team"
    engine = _make_engine()
    draft_state = _make_draft_state(current_pick=50)

    # Create a player that improves the target category
    is_pitching = category in ('ERA', 'K', 'SHOLDS', 'WHIP', 'WQS')
    if is_pitching:
        if category == 'ERA':
            # Lower ERA improves the category
            player = _make_pitcher("improver", projected_era=2.00, projected_whip=1.20,
                                   projected_strikeouts=200.0, projected_wins=10.0,
                                   projected_quality_starts=15.0, projected_saves=0.0,
                                   projected_holds=0.0)
        elif category == 'WHIP':
            player = _make_pitcher("improver", projected_era=3.50, projected_whip=0.90,
                                   projected_strikeouts=200.0, projected_wins=10.0,
                                   projected_quality_starts=15.0, projected_saves=0.0,
                                   projected_holds=0.0)
        elif category == 'K':
            player = _make_pitcher("improver", projected_era=3.50, projected_whip=1.20,
                                   projected_strikeouts=300.0, projected_wins=10.0,
                                   projected_quality_starts=15.0, projected_saves=0.0,
                                   projected_holds=0.0)
        elif category == 'WQS':
            player = _make_pitcher("improver", projected_era=3.50, projected_whip=1.20,
                                   projected_strikeouts=100.0, projected_wins=20.0,
                                   projected_quality_starts=20.0, projected_saves=0.0,
                                   projected_holds=0.0)
        else:  # SHOLDS
            player = _make_pitcher("improver", projected_era=3.50, projected_whip=1.20,
                                   projected_strikeouts=100.0, projected_wins=5.0,
                                   projected_quality_starts=5.0, projected_saves=40.0,
                                   projected_holds=10.0)
    else:
        if category == 'HR':
            player = _make_hitter("improver", projected_home_runs=50.0)
        elif category == 'OBP':
            player = _make_hitter("improver", projected_obp=0.420)
        elif category == 'R':
            player = _make_hitter("improver", projected_runs=120.0)
        elif category == 'RBI':
            player = _make_hitter("improver", projected_rbi=120.0)
        else:  # SB
            player = _make_hitter("improver", projected_stolen_bases=50.0)

    # Scenario 1: team ranks in bottom third
    rosters_bottom, my_team_bottom = _build_rosters_for_rank(
        team_name, category, bottom_rank
    )
    score_bottom, _ = engine._score_relative_advantage(
        player, my_team_bottom, rosters_bottom, draft_state, team_name=team_name
    )

    # Scenario 2: team ranks in top third
    rosters_top, my_team_top = _build_rosters_for_rank(
        team_name, category, top_rank
    )
    score_top, _ = engine._score_relative_advantage(
        player, my_team_top, rosters_top, draft_state, team_name=team_name
    )

    assert score_bottom >= score_top, (
        f"Bottom-third bonus should be >= top-third bonus. "
        f"Category={category}, bottom_rank={bottom_rank}, top_rank={top_rank}, "
        f"score_bottom={score_bottom}, score_top={score_top}"
    )


# ---------------------------------------------------------------------------
# Property 20: ADP value monotonicity
# Feature: recommendation-engine-rebuild, Property 20: ADP value monotonicity
#
# For any player with ADP data, the ADP value score should be positive when
# ADP > current_pick (value pick), negative when ADP < current_pick (reach),
# and the magnitude should increase with the size of the gap.
#
# **Validates: Requirements 9.1, 9.2, 9.4**
# ---------------------------------------------------------------------------


def _make_draft_state_with_picks(num_picks):
    """Create a DraftState with a specific number of picks already made."""
    from src.models.draft import DraftPick
    ds = DraftState(
        draft_id="test_draft",
        league_name="Test League",
        total_teams=13,
        roster_size=21,
        my_team_name="My Team",
        current_pick=num_picks + 1,
        current_round=(num_picks) // 13 + 1,
    )
    # Add dummy picks so len(picks) == num_picks
    for i in range(num_picks):
        ds.picks.append(DraftPick(
            pick_number=i + 1,
            round=(i // 13) + 1,
            team_name=f"Team_{i % 13}",
            player_id=f"player_{i}",
        ))
    return ds


@given(
    adp=st.floats(min_value=2.0, max_value=300.0),
    current_pick_offset=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100)
def test_adp_value_positive_when_player_has_fallen(adp, current_pick_offset):
    """Property 20: When current_pick > ADP, the player has fallen past their
    ADP and the score should be positive (value / steal).

    **Validates: Requirement 9.1**
    """
    # current_pick > adp → player has fallen past ADP → value
    current_pick = int(adp) + current_pick_offset
    assume(current_pick >= 1)
    assume(current_pick > adp)

    engine = _make_engine()
    draft_state = _make_draft_state_with_picks(current_pick - 1)

    player = _make_hitter("target", adp=adp)

    score, reasoning = engine._score_adp_value(player, draft_state)

    assert score > 0, (
        f"ADP value should be positive when current_pick ({current_pick}) > ADP ({adp}) "
        f"(player has fallen). Got score={score}. Reasoning: {reasoning}"
    )


@given(
    current_pick=st.integers(min_value=2, max_value=250),
    reach=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100)
def test_adp_value_negative_when_reaching(current_pick, reach):
    """Property 20: When current_pick < ADP, we're reaching for the player
    (picking them before their ADP) and the score should be negative.

    **Validates: Requirement 9.2**
    """
    adp = float(current_pick + reach)

    engine = _make_engine()
    draft_state = _make_draft_state_with_picks(current_pick - 1)

    player = _make_hitter("target", adp=adp)

    score, reasoning = engine._score_adp_value(player, draft_state)

    assert score < 0, (
        f"ADP value should be negative when current_pick ({current_pick}) < ADP ({adp}) "
        f"(reaching). Got score={score}. Reasoning: {reasoning}"
    )


@given(
    current_pick=st.integers(min_value=10, max_value=200),
    gap_small=st.integers(min_value=1, max_value=20),
    gap_extra=st.integers(min_value=1, max_value=30),
)
@settings(max_examples=100)
def test_adp_value_magnitude_increases_with_gap(current_pick, gap_small, gap_extra):
    """Property 20: The magnitude of the ADP value score should increase with
    the size of the gap (both for value picks and reaches).

    Value: current_pick > ADP (player has fallen) → positive score
    Reach: current_pick < ADP (picking early) → negative score

    **Validates: Requirements 9.1, 9.2, 9.4**
    """
    gap_large = gap_small + gap_extra

    engine = _make_engine()
    draft_state = _make_draft_state_with_picks(current_pick - 1)

    # Test value picks: player has fallen past ADP (ADP < current_pick)
    # Larger fall → higher positive score
    adp_small_value = float(current_pick - gap_small)
    adp_large_value = float(current_pick - gap_large)
    assume(adp_small_value >= 1.0)
    assume(adp_large_value >= 1.0)

    player_small_value = _make_hitter("small_val", adp=adp_small_value)
    player_large_value = _make_hitter("large_val", adp=adp_large_value)

    score_small_value, _ = engine._score_adp_value(player_small_value, draft_state)
    score_large_value, _ = engine._score_adp_value(player_large_value, draft_state)

    assert score_large_value > score_small_value, (
        f"Larger value gap should yield higher score. "
        f"gap_small={gap_small} (score={score_small_value}), "
        f"gap_large={gap_large} (score={score_large_value})"
    )

    # Test reaches: picking before ADP (ADP > current_pick)
    # Larger reach → more negative score (larger magnitude)
    adp_small_reach = float(current_pick + gap_small)
    adp_large_reach = float(current_pick + gap_large)

    player_small_reach = _make_hitter("small_reach", adp=adp_small_reach)
    player_large_reach = _make_hitter("large_reach", adp=adp_large_reach)

    score_small_reach, _ = engine._score_adp_value(player_small_reach, draft_state)
    score_large_reach, _ = engine._score_adp_value(player_large_reach, draft_state)

    assert abs(score_large_reach) > abs(score_small_reach), (
        f"Larger reach gap should yield larger magnitude penalty. "
        f"gap_small={gap_small} (score={score_small_reach}), "
        f"gap_large={gap_large} (score={score_large_reach})"
    )


@given(
    current_pick=st.integers(min_value=1, max_value=250),
)
@settings(max_examples=100)
def test_adp_value_none_returns_zero(current_pick):
    """Property 20: When ADP is None, the score should be 0.0.

    **Validates: Requirement 9.3**
    """
    engine = _make_engine()
    draft_state = _make_draft_state_with_picks(current_pick - 1)

    player = _make_hitter("target", adp=None)

    score, reasoning = engine._score_adp_value(player, draft_state)

    assert score == 0.0, (
        f"ADP value should be 0.0 when ADP is None. Got score={score}"
    )
    assert "No ADP data" in reasoning

# ---------------------------------------------------------------------------
# Property 21: Pitcher cap penalty increases with pitcher count
# Feature: recommendation-engine-rebuild, Property 21: Pitcher cap penalty increases with count
#
# For any team, the pitcher cap penalty for adding another pitcher should be
# more negative when the team has 9+ pitchers than when the team has 7–8
# pitchers, and zero or positive when the team has fewer than 7 pitchers.
#
# **Validates: Requirements 10.1, 10.2**
# ---------------------------------------------------------------------------


@given(
    current_pick=st.integers(min_value=1, max_value=250),
)
@settings(max_examples=100)
def test_pitcher_cap_penalty_increases_with_count(current_pick):
    """Property 21: Penalty at 9+ pitchers > penalty at 7-8 > penalty at <7.

    **Validates: Requirements 10.1, 10.2**
    """
    engine = _make_engine()
    draft_state = _make_draft_state_with_picks(current_pick - 1)

    # The candidate pitcher (non-closer so closer bonus doesn't interfere)
    candidate = _make_pitcher("candidate_sp", projected_saves=0.0, projected_holds=0.0)

    # Team with 6 pitchers (below threshold)
    team_6p = [_make_pitcher(f"p6_{i}") for i in range(6)]
    score_6, _ = engine._score_pitcher_caps(candidate, team_6p, draft_state)

    # Team with 7 pitchers (7-8 range)
    team_7p = [_make_pitcher(f"p7_{i}") for i in range(7)]
    score_7, _ = engine._score_pitcher_caps(candidate, team_7p, draft_state)

    # Team with 8 pitchers (7-8 range)
    team_8p = [_make_pitcher(f"p8_{i}") for i in range(8)]
    score_8, _ = engine._score_pitcher_caps(candidate, team_8p, draft_state)

    # Team with 9 pitchers (9+ range)
    team_9p = [_make_pitcher(f"p9_{i}") for i in range(9)]
    score_9, _ = engine._score_pitcher_caps(candidate, team_9p, draft_state)

    # Team with 10 pitchers (9+ range)
    team_10p = [_make_pitcher(f"p10_{i}") for i in range(10)]
    score_10, _ = engine._score_pitcher_caps(candidate, team_10p, draft_state)

    # <7 pitchers: no penalty (score >= 0)
    assert score_6 >= 0, f"Expected no penalty at 6 pitchers, got {score_6}"

    # 7-8 pitchers: moderate penalty
    assert score_7 < score_6, (
        f"Penalty at 7 pitchers ({score_7}) should be worse than at 6 ({score_6})"
    )
    assert score_8 < score_6, (
        f"Penalty at 8 pitchers ({score_8}) should be worse than at 6 ({score_6})"
    )

    # 9+ pitchers: larger penalty than 7-8
    assert score_9 < score_7, (
        f"Penalty at 9 pitchers ({score_9}) should be worse than at 7 ({score_7})"
    )
    assert score_10 < score_8, (
        f"Penalty at 10 pitchers ({score_10}) should be worse than at 8 ({score_8})"
    )


# ---------------------------------------------------------------------------
# Property 22: Closer bonus decreases with closer count
# Feature: recommendation-engine-rebuild, Property 22: Closer bonus decreases with closer count
#
# For any closer-eligible player (projected_saves >= 10), the closer bonus
# should be largest when the team has 0 closers (after pick 80), smaller
# with 1 closer (after pick 130), and smallest with 2 closers (after pick 180).
#
# **Validates: Requirements 10.3, 10.4, 10.5**
# ---------------------------------------------------------------------------


@given(
    projected_saves=st.floats(min_value=10.0, max_value=50.0),
)
@settings(max_examples=100)
def test_closer_bonus_decreases_with_closer_count(projected_saves):
    """Property 22: Closer bonus is largest at 0 closers, smaller at 1, smallest at 2.

    We test at pick 200 (past all thresholds: 80, 130, 180) so all tiers
    are active. We keep pitcher count at 5 (below 7) to avoid cap penalties
    interfering with the closer bonus comparison.

    **Validates: Requirements 10.3, 10.4, 10.5**
    """
    engine = _make_engine()
    # Pick 200 is past all closer thresholds
    draft_state = _make_draft_state_with_picks(199)

    candidate = _make_pitcher(
        "closer_candidate", position="RP",
        projected_saves=projected_saves, projected_holds=0.0,
    )

    # Helper to build a team with a given number of closers (and fill rest with non-closers)
    def _team_with_closers(n_closers, total_pitchers=5):
        team = []
        for i in range(n_closers):
            team.append(_make_pitcher(
                f"closer_{i}", position="RP",
                projected_saves=25.0, projected_holds=0.0,
            ))
        for i in range(total_pitchers - n_closers):
            team.append(_make_pitcher(
                f"sp_{i}", position="SP",
                projected_saves=0.0, projected_holds=0.0,
            ))
        return team

    score_0_closers, _ = engine._score_pitcher_caps(
        candidate, _team_with_closers(0), draft_state
    )
    score_1_closer, _ = engine._score_pitcher_caps(
        candidate, _team_with_closers(1), draft_state
    )
    score_2_closers, _ = engine._score_pitcher_caps(
        candidate, _team_with_closers(2), draft_state
    )

    assert score_0_closers > score_1_closer, (
        f"Bonus at 0 closers ({score_0_closers}) should exceed bonus at 1 closer ({score_1_closer})"
    )
    assert score_1_closer > score_2_closers, (
        f"Bonus at 1 closer ({score_1_closer}) should exceed bonus at 2 closers ({score_2_closers})"
    )


# ---------------------------------------------------------------------------
# Property 23: Category balance activates at 5+ players
# Feature: recommendation-engine-rebuild, Property 23: Category balance activates at 5+ players
#
# For any team with fewer than 5 drafted players, the category balance score
# should be zero. For any team with 5+ players losing to 8+ opponents in a
# category, a player improving that category should receive a positive
# balance bonus.
#
# **Validates: Requirements 11.1, 11.2**
# ---------------------------------------------------------------------------


@given(
    team_size=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_category_balance_zero_below_5_players(team_size):
    """Property 23 (part 1): Category balance score is zero when team has < 5 players.

    **Validates: Requirement 11.1**
    """
    engine = _make_engine()
    team_name = "My Team"

    my_team = [_make_hitter(f"h_{i}") for i in range(team_size)]
    candidate = _make_hitter("candidate", projected_home_runs=50.0)

    # Build opponent rosters (doesn't matter what they are — should still be 0)
    all_team_rosters = {team_name: my_team}
    for t in range(12):
        all_team_rosters[f"Opp_{t}"] = [
            _make_hitter(f"opp_{t}_h", projected_home_runs=40.0)
        ]

    score, reasoning = engine._score_category_balance(
        candidate, my_team, all_team_rosters, team_name
    )

    assert score == 0.0, (
        f"Category balance should be 0.0 with {team_size} players, got {score}"
    )


@given(
    category=st.sampled_from(['HR', 'R', 'RBI', 'SB']),
    extra_opponents=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_category_balance_positive_when_losing_to_8_plus(category, extra_opponents):
    """Property 23 (part 2): Positive balance bonus when team has 5+ players
    and is losing to 8+ opponents in a counting category, and the candidate
    improves that category.

    **Validates: Requirements 11.1, 11.2**
    """
    engine = _make_engine()
    team_name = "My Team"
    opponents_beating = 8 + extra_opponents  # 8 to 12

    # Build my team with 5 hitters that have LOW values in the target category
    low_val = 5.0
    cat_kwargs = {
        'HR': {'projected_home_runs': low_val},
        'R': {'projected_runs': low_val},
        'RBI': {'projected_rbi': low_val},
        'SB': {'projected_stolen_bases': low_val},
    }
    my_team = [
        _make_hitter(f"my_h_{i}", **cat_kwargs[category])
        for i in range(5)
    ]

    # Build a candidate that clearly improves the weak category
    strong_kwargs = {
        'HR': {'projected_home_runs': 50.0},
        'R': {'projected_runs': 120.0},
        'RBI': {'projected_rbi': 120.0},
        'SB': {'projected_stolen_bases': 50.0},
    }
    candidate = _make_hitter("candidate", **strong_kwargs[category])

    # Build opponent rosters: `opponents_beating` teams beat us, rest don't
    high_val = low_val * 10  # opponents clearly beat us
    all_team_rosters = {team_name: my_team}
    for t in range(12):
        if t < opponents_beating:
            # This opponent beats us in the target category
            opp_kwargs = {
                'HR': {'projected_home_runs': high_val},
                'R': {'projected_runs': high_val},
                'RBI': {'projected_rbi': high_val},
                'SB': {'projected_stolen_bases': high_val},
            }
            all_team_rosters[f"Opp_{t}"] = [
                _make_hitter(f"opp_{t}_h", **opp_kwargs[category])
            ]
        else:
            # This opponent does NOT beat us
            all_team_rosters[f"Opp_{t}"] = [
                _make_hitter(f"opp_{t}_h", **cat_kwargs[category])
            ]

    score, reasoning = engine._score_category_balance(
        candidate, my_team, all_team_rosters, team_name
    )

    assert score > 0.0, (
        f"Expected positive balance bonus when losing to {opponents_beating} "
        f"opponents in {category}, got score={score}"
    )


@given(
    category=st.sampled_from(['ERA', 'WHIP']),
    extra_opponents=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_category_balance_rate_stats_losing_to_8_plus(category, extra_opponents):
    """Property 23 (part 2, rate stats): Positive balance bonus for ERA/WHIP
    when team has 5+ players and is losing to 8+ opponents, and the candidate
    pitcher improves (lowers) the rate stat.

    **Validates: Requirements 11.1, 11.2**
    """
    engine = _make_engine()
    team_name = "My Team"
    opponents_beating = 8 + extra_opponents  # 8 to 12

    # My team: 5 hitters + 1 pitcher with BAD ERA/WHIP
    bad_era, bad_whip = 6.00, 1.80
    my_hitters = [_make_hitter(f"my_h_{i}") for i in range(5)]
    my_pitcher = _make_pitcher(
        "my_p", projected_era=bad_era, projected_whip=bad_whip,
    )
    my_team = my_hitters + [my_pitcher]

    # Candidate pitcher that improves the rate stat
    if category == 'ERA':
        candidate = _make_pitcher("candidate_p", projected_era=2.50, projected_whip=1.20)
    else:
        candidate = _make_pitcher("candidate_p", projected_era=3.50, projected_whip=0.95)

    # Build opponent rosters
    good_era, good_whip = 3.00, 1.10
    all_team_rosters = {team_name: my_team}
    for t in range(12):
        if t < opponents_beating:
            # Opponent beats us (lower ERA/WHIP)
            all_team_rosters[f"Opp_{t}"] = [
                _make_pitcher(
                    f"opp_{t}_p", projected_era=good_era, projected_whip=good_whip,
                )
            ]
        else:
            # Opponent does NOT beat us (worse ERA/WHIP)
            all_team_rosters[f"Opp_{t}"] = [
                _make_pitcher(
                    f"opp_{t}_p", projected_era=bad_era + 1.0, projected_whip=bad_whip + 0.2,
                )
            ]

    score, reasoning = engine._score_category_balance(
        candidate, my_team, all_team_rosters, team_name
    )

    assert score > 0.0, (
        f"Expected positive balance bonus for {category} when losing to "
        f"{opponents_beating} opponents, got score={score}"
    )
