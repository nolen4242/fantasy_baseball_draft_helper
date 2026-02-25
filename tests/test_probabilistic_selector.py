"""
Property-based tests for probabilistic player selection.

Feature: auto-draft-variability
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, assume, settings
from collections import Counter

from src.services.probabilistic_selector import ProbabilisticSelector
from src.services.variability_config import VariabilityConfig
from src.models.player import Player


# Helper function to create mock candidates
def create_mock_candidates(num_candidates: int, scores: list = None) -> list:
    """Create a list of mock candidate dictionaries."""
    if scores is None:
        scores = list(range(num_candidates, 0, -1))  # Descending scores
    
    candidates = []
    for i, score in enumerate(scores):
        player = Player(
            player_id=f"player_{i}",
            name=f"Player {i}",
            position="OF",
            team="TEST"
        )
        candidates.append({
            'player': player,
            'score': score,
            'reasoning': f"Test reasoning for player {i}"
        })
    
    return candidates


# Property 1: Probability Distribution Validity
# Validates: Requirements 1.5, 6.5
@given(
    num_scores=st.integers(min_value=1, max_value=20),
    temperature=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=100)
def test_property_probability_distribution_validity(num_scores, temperature, seed):
    """
    Property 1: Probability Distribution Validity
    
    For any set of candidate scores and temperature value, the softmax function 
    with temperature scaling should produce a valid probability distribution where 
    all probabilities are non-negative, finite, and sum to 1.0 (within numerical tolerance).
    
    Validates: Requirements 1.5, 6.5
    """
    # Create config and selector
    config = VariabilityConfig()
    random_state = np.random.RandomState(seed)
    selector = ProbabilisticSelector(config, random_state)
    
    # Generate random scores
    scores = np.random.RandomState(seed + 1).uniform(0.0, 100.0, num_scores)
    
    # Apply softmax with temperature
    probabilities = selector._softmax_with_temperature(scores, temperature)
    
    # Property 1: All probabilities must be non-negative
    assert np.all(probabilities >= 0.0), \
        f"Found negative probabilities: {probabilities}"
    
    # Property 2: All probabilities must be finite
    assert np.all(np.isfinite(probabilities)), \
        f"Found non-finite probabilities: {probabilities}"
    
    # Property 3: Probabilities must sum to 1.0 (within numerical tolerance)
    prob_sum = np.sum(probabilities)
    assert abs(prob_sum - 1.0) < 1e-6, \
        f"Probabilities sum to {prob_sum}, expected 1.0"
    
    # Property 4: Number of probabilities matches number of scores
    assert len(probabilities) == len(scores), \
        f"Expected {len(scores)} probabilities, got {len(probabilities)}"


# Property 2: Temperature Monotonicity
# Validates: Requirements 6.2, 6.3, 6.4
@given(
    num_scores=st.integers(min_value=2, max_value=10),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=100)
def test_property_temperature_monotonicity(num_scores, seed):
    """
    Property 2: Temperature Monotonicity
    
    For any set of candidate scores, as temperature increases, the entropy of 
    the probability distribution should increase (distribution becomes more uniform), 
    and when temperature is 0.0, the highest-scored candidate should have probability 1.0.
    
    Validates: Requirements 6.2, 6.3, 6.4
    """
    # Create config and selector
    config = VariabilityConfig()
    random_state = np.random.RandomState(seed)
    selector = ProbabilisticSelector(config, random_state)
    
    # Generate random scores with distinct values
    scores = np.random.RandomState(seed + 1).uniform(0.0, 100.0, num_scores)
    scores = np.sort(scores)[::-1]  # Sort descending to ensure distinct ordering
    
    # Ensure scores are distinct
    assume(len(np.unique(scores)) == len(scores))
    
    # Test temperature = 0.0 (deterministic)
    probs_zero = selector._softmax_with_temperature(scores, 0.0)
    max_idx = np.argmax(scores)
    assert probs_zero[max_idx] == 1.0, \
        f"At temperature 0.0, highest score should have probability 1.0, got {probs_zero[max_idx]}"
    assert np.sum(probs_zero) == 1.0, \
        f"Probabilities should sum to 1.0, got {np.sum(probs_zero)}"
    
    # Test increasing temperature increases entropy
    def entropy(probs):
        """Calculate Shannon entropy of probability distribution."""
        # Filter out zero probabilities to avoid log(0)
        probs_nonzero = probs[probs > 0]
        return -np.sum(probs_nonzero * np.log(probs_nonzero))
    
    temp_low = 0.5
    temp_high = 1.5
    
    probs_low = selector._softmax_with_temperature(scores, temp_low)
    probs_high = selector._softmax_with_temperature(scores, temp_high)
    
    entropy_low = entropy(probs_low)
    entropy_high = entropy(probs_high)
    
    # Property: Higher temperature should have higher or equal entropy
    assert entropy_high >= entropy_low - 1e-6, \
        f"Entropy should increase with temperature: {entropy_low} -> {entropy_high}"


# Property 3: Top-N Candidate Selection
# Validates: Requirements 1.4
@given(
    num_candidates=st.integers(min_value=5, max_value=20),
    top_n=st.integers(min_value=1, max_value=10),
    round_num=st.integers(min_value=1, max_value=30),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=100)
def test_property_top_n_candidate_selection(num_candidates, top_n, round_num, seed):
    """
    Property 3: Top-N Candidate Selection
    
    For any candidate list and configuration, when making an optimal pick, 
    the selected player should always be from the top N candidates (where N is configurable).
    
    Validates: Requirements 1.4
    """
    # Create config with specified top_n
    config = VariabilityConfig(
        top_n_candidates=top_n,
        mistake_rate_early=0.0,  # No mistakes for this test
        mistake_rate_mid=0.0,
        mistake_rate_late=0.0
    )
    random_state = np.random.RandomState(seed)
    selector = ProbabilisticSelector(config, random_state)
    
    # Create candidates with descending scores
    candidates = create_mock_candidates(num_candidates)
    
    # Make a selection
    selected_player, reasoning = selector.select_player(candidates, round_num, "Test Team")
    
    # Property: Selected player should be in top N candidates
    top_n_actual = min(top_n, num_candidates)
    top_n_player_ids = [c['player'].player_id for c in candidates[:top_n_actual]]
    
    assert selected_player.player_id in top_n_player_ids, \
        f"Selected player {selected_player.player_id} not in top {top_n_actual} candidates: {top_n_player_ids}"
    
    # Property: Reasoning should mention probabilistic selection
    assert "Probabilistic selection" in reasoning, \
        f"Reasoning should mention probabilistic selection: {reasoning}"


# Property 4: Probabilistic Selection Bias
# Validates: Requirements 1.2
@given(
    num_candidates=st.integers(min_value=3, max_value=5),
    temperature=st.floats(min_value=0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=50)
def test_property_probabilistic_selection_bias(num_candidates, temperature, seed):
    """
    Property 4: Probabilistic Selection Bias
    
    For any candidate list with distinct scores, over many selections with the same 
    temperature, higher-scored candidates should be selected more frequently than 
    lower-scored candidates.
    
    Validates: Requirements 1.2
    """
    # Create config with specified temperature and no mistakes
    config = VariabilityConfig(
        top_n_candidates=num_candidates,
        temperature_early_rounds=temperature,
        temperature_mid_rounds=temperature,
        temperature_late_rounds=temperature,
        mistake_rate_early=0.0,
        mistake_rate_mid=0.0,
        mistake_rate_late=0.0
    )
    
    # Create candidates with clearly distinct scores
    scores = [100.0 - i * 10.0 for i in range(num_candidates)]
    candidates = create_mock_candidates(num_candidates, scores)
    
    # Run many selections
    num_trials = 200
    selection_counts = Counter()
    
    for trial in range(num_trials):
        random_state = np.random.RandomState(seed + trial)
        selector = ProbabilisticSelector(config, random_state)
        selected_player, _ = selector.select_player(candidates, 10, "Test Team")
        selection_counts[selected_player.player_id] += 1
    
    # Property: Higher-scored candidates should be selected more frequently
    # Check that the top candidate is selected more than the bottom candidate
    top_player_id = candidates[0]['player'].player_id
    bottom_player_id = candidates[-1]['player'].player_id
    
    top_count = selection_counts[top_player_id]
    bottom_count = selection_counts[bottom_player_id]
    
    assert top_count > bottom_count, \
        f"Top candidate (score {scores[0]}) selected {top_count} times, " \
        f"bottom candidate (score {scores[-1]}) selected {bottom_count} times. " \
        f"Expected top > bottom."


# Property 11: Suboptimal Pick Range Validity
# Validates: Requirements 4.3, 4.4
@given(
    num_candidates=st.integers(min_value=20, max_value=30),
    min_rank=st.integers(min_value=6, max_value=10),
    max_rank=st.integers(min_value=11, max_value=20),
    round_num=st.integers(min_value=1, max_value=30),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=100)
def test_property_suboptimal_pick_range_validity(num_candidates, min_rank, max_rank, round_num, seed):
    """
    Property 11: Suboptimal Pick Range Validity
    
    For any suboptimal pick, the selected player's rank must be within the 
    configured suboptimal_range, and the player must satisfy roster constraints.
    
    Validates: Requirements 4.3, 4.4
    """
    assume(min_rank < max_rank)
    assume(max_rank <= num_candidates)
    
    # Create config with suboptimal range and 100% mistake rate
    config = VariabilityConfig(
        suboptimal_range=(min_rank, max_rank),
        mistake_rate_early=1.0,  # Always make suboptimal picks
        mistake_rate_mid=1.0,
        mistake_rate_late=1.0
    )
    random_state = np.random.RandomState(seed)
    selector = ProbabilisticSelector(config, random_state)
    
    # Create candidates
    candidates = create_mock_candidates(num_candidates)
    
    # Make a selection (should be suboptimal)
    selected_player, reasoning = selector.select_player(candidates, round_num, "Test Team")
    
    # Property: Selected player should be in suboptimal range
    player_ids_in_range = [c['player'].player_id for c in candidates[min_rank-1:max_rank]]
    
    assert selected_player.player_id in player_ids_in_range, \
        f"Suboptimal pick {selected_player.player_id} not in range [{min_rank}, {max_rank})"
    
    # Property: Reasoning should mention suboptimal pick
    assert "SUBOPTIMAL PICK" in reasoning, \
        f"Reasoning should mention suboptimal pick: {reasoning}"
    
    # Property: Reasoning should mention the rank range
    assert f"rank {min_rank}-{max_rank}" in reasoning, \
        f"Reasoning should mention rank range: {reasoning}"


# Property 10: Mistake Rate Frequency
# Validates: Requirements 4.2
@given(
    round_num=st.integers(min_value=1, max_value=30),
    mistake_rate=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=1000000)
)
@settings(max_examples=50)
def test_property_mistake_rate_frequency(round_num, mistake_rate, seed):
    """
    Property 10: Mistake Rate Frequency
    
    For any round number and mistake rate, over many picks, the frequency of 
    suboptimal picks should converge to the configured mistake rate for that round.
    
    Validates: Requirements 4.2
    """
    # Create config with specified mistake rate
    config = VariabilityConfig(
        mistake_rate_early=mistake_rate,
        mistake_rate_mid=mistake_rate,
        mistake_rate_late=mistake_rate,
        suboptimal_range=(6, 15)
    )
    
    # Create candidates (need enough for suboptimal range)
    num_candidates = 20
    candidates = create_mock_candidates(num_candidates)
    
    # Run many selections
    num_trials = 500
    suboptimal_count = 0
    
    for trial in range(num_trials):
        random_state = np.random.RandomState(seed + trial)
        selector = ProbabilisticSelector(config, random_state)
        _, reasoning = selector.select_player(candidates, round_num, "Test Team")
        
        if "SUBOPTIMAL PICK" in reasoning:
            suboptimal_count += 1
    
    # Calculate observed frequency
    observed_frequency = suboptimal_count / num_trials
    
    # Property: Observed frequency should be close to configured mistake rate
    # Allow 10% tolerance (e.g., if mistake_rate=0.3, accept 0.27-0.33)
    tolerance = 0.10
    lower_bound = mistake_rate - tolerance
    upper_bound = mistake_rate + tolerance
    
    assert lower_bound <= observed_frequency <= upper_bound, \
        f"Observed suboptimal frequency {observed_frequency:.3f} not within " \
        f"tolerance of configured rate {mistake_rate:.3f} " \
        f"(expected {lower_bound:.3f} to {upper_bound:.3f})"


# Unit tests for edge cases

def test_empty_candidates_raises_error():
    """
    Unit test: Selecting from empty candidate list should raise ValueError.
    
    Validates: Requirements 1.1
    """
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    selector = ProbabilisticSelector(config, random_state)
    
    with pytest.raises(ValueError, match="No candidates provided"):
        selector.select_player([], 1, "Test Team")


def test_single_candidate_selection():
    """
    Unit test: Selecting from single candidate should return that candidate.
    
    Validates: Requirements 1.1
    """
    config = VariabilityConfig(mistake_rate_early=0.0, mistake_rate_mid=0.0, mistake_rate_late=0.0)
    random_state = np.random.RandomState(42)
    selector = ProbabilisticSelector(config, random_state)
    
    candidates = create_mock_candidates(1)
    selected_player, reasoning = selector.select_player(candidates, 1, "Test Team")
    
    assert selected_player.player_id == "player_0"
    assert "Probabilistic selection" in reasoning


def test_suboptimal_fallback_when_range_exceeds_candidates():
    """
    Unit test: When suboptimal range exceeds candidate list, should fall back to optimal selection.
    
    Validates: Requirements 4.4
    """
    config = VariabilityConfig(
        suboptimal_range=(10, 20),
        mistake_rate_early=1.0,  # Always try suboptimal
        mistake_rate_mid=1.0,
        mistake_rate_late=1.0
    )
    random_state = np.random.RandomState(42)
    selector = ProbabilisticSelector(config, random_state)
    
    # Only 5 candidates, suboptimal range starts at 10
    candidates = create_mock_candidates(5)
    selected_player, reasoning = selector.select_player(candidates, 1, "Test Team")
    
    # Should fall back to optimal selection
    assert "Probabilistic selection" in reasoning
    assert "SUBOPTIMAL PICK" not in reasoning


def test_temperature_zero_is_deterministic():
    """
    Unit test: Temperature of 0.0 should always select the highest-scored candidate.
    
    Validates: Requirements 6.2
    """
    config = VariabilityConfig(
        temperature_early_rounds=0.0,
        temperature_mid_rounds=0.0,
        temperature_late_rounds=0.0,
        mistake_rate_early=0.0,
        mistake_rate_mid=0.0,
        mistake_rate_late=0.0,
        top_n_candidates=5
    )
    
    candidates = create_mock_candidates(10)
    
    # Run multiple times with different seeds
    selected_ids = set()
    for seed in range(10):
        random_state = np.random.RandomState(seed)
        selector = ProbabilisticSelector(config, random_state)
        selected_player, _ = selector.select_player(candidates, 1, "Test Team")
        selected_ids.add(selected_player.player_id)
    
    # Should always select the same (highest-scored) player
    assert len(selected_ids) == 1, \
        f"Temperature 0.0 should be deterministic, got {len(selected_ids)} different selections"
    assert "player_0" in selected_ids, \
        "Should select the highest-scored candidate (player_0)"


def test_softmax_numerical_stability():
    """
    Unit test: Softmax should handle large score differences without overflow.
    
    Validates: Requirements 1.5, 6.5
    """
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    selector = ProbabilisticSelector(config, random_state)
    
    # Create scores with large differences
    scores = np.array([1000.0, 500.0, 100.0, 10.0, 1.0])
    
    probabilities = selector._softmax_with_temperature(scores, 1.0)
    
    # Should not have NaN or Inf
    assert np.all(np.isfinite(probabilities))
    
    # Should sum to 1.0
    assert abs(np.sum(probabilities) - 1.0) < 1e-6
    
    # Should be non-negative
    assert np.all(probabilities >= 0.0)
