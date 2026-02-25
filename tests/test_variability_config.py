"""
Property-based tests for variability configuration.

Feature: auto-draft-variability
"""

import pytest
from hypothesis import given, strategies as st, assume
from src.services.variability_config import StrategyProfile, VariabilityConfig, STRATEGY_PROFILES


# Property 7: Strategy Weight Validity
# Validates: Requirements 2.5
@given(
    adp_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    team_needs_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    position_scarcity_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_property_strategy_weight_validity(adp_weight, team_needs_weight, position_scarcity_weight):
    """
    Property 7: Strategy Weight Validity
    
    For any strategy profile, the sum of adp_weight, team_needs_weight, and 
    position_scarcity_weight must equal 1.0 (within tolerance of 0.01), and 
    all weights must be non-negative.
    
    Validates: Requirements 2.5
    """
    # Create a strategy profile with the generated weights
    strategy = StrategyProfile(
        name="test_strategy",
        description="Test strategy",
        adp_weight=adp_weight,
        team_needs_weight=team_needs_weight,
        position_scarcity_weight=position_scarcity_weight
    )
    
    # Validate the strategy
    errors = strategy.validate()
    
    # Calculate the weight sum
    weight_sum = adp_weight + team_needs_weight + position_scarcity_weight
    
    # Property: If weights sum to 1.0 (within tolerance), validation should pass for weight sum
    if abs(weight_sum - 1.0) <= 0.01:
        # Should not have weight sum error
        assert not any("must sum to 1.0" in error for error in errors), \
            f"Valid weight sum {weight_sum:.4f} incorrectly flagged as invalid"
    else:
        # Should have weight sum error
        assert any("must sum to 1.0" in error for error in errors), \
            f"Invalid weight sum {weight_sum:.4f} not detected"
    
    # Property: All weights are in [0.0, 1.0] range (already constrained by hypothesis)
    # No range errors should occur for individual weights since they're in valid range
    assert not any("adp_weight must be between" in error for error in errors)
    assert not any("team_needs_weight must be between" in error for error in errors)
    assert not any("position_scarcity_weight must be between" in error for error in errors)


@given(
    hitter_pref=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    pitcher_pref=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    power_pref=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_property_strategy_preference_validity(hitter_pref, pitcher_pref, power_pref):
    """
    Property 7 (extended): Strategy Preference Validity
    
    For any strategy profile, all preference multipliers must be non-negative.
    
    Validates: Requirements 2.5
    """
    # Create a strategy with valid weights but test preferences
    strategy = StrategyProfile(
        name="test_strategy",
        description="Test strategy",
        adp_weight=0.6,
        team_needs_weight=0.3,
        position_scarcity_weight=0.1,
        hitter_preference=hitter_pref,
        pitcher_preference=pitcher_pref,
        power_preference=power_pref
    )
    
    errors = strategy.validate()
    
    # Property: Negative preferences should be flagged
    if hitter_pref < 0:
        assert any("hitter_preference must be non-negative" in error for error in errors)
    else:
        assert not any("hitter_preference must be non-negative" in error for error in errors)
    
    if pitcher_pref < 0:
        assert any("pitcher_preference must be non-negative" in error for error in errors)
    else:
        assert not any("pitcher_preference must be non-negative" in error for error in errors)
    
    if power_pref < 0:
        assert any("power_preference must be non-negative" in error for error in errors)
    else:
        assert not any("power_preference must be non-negative" in error for error in errors)


def test_predefined_strategies_are_valid():
    """
    Unit test: All predefined strategy profiles should be valid.
    
    Validates: Requirements 2.1, 2.4, 5.1, 5.2, 5.3, 5.4, 5.5
    """
    for name, strategy in STRATEGY_PROFILES.items():
        errors = strategy.validate()
        assert len(errors) == 0, f"Predefined strategy '{name}' has validation errors: {errors}"


def test_predefined_strategies_exist():
    """
    Unit test: All required predefined strategies should exist.
    
    Validates: Requirements 2.1, 2.4
    """
    required_strategies = ['balanced', 'aggressive_hitters', 'pitcher_heavy', 'value_focused', 'position_scarcity']
    
    for strategy_name in required_strategies:
        assert strategy_name in STRATEGY_PROFILES, f"Required strategy '{strategy_name}' not found"


# Property 12: Round-Based Parameter Consistency
# Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
@given(
    round_num=st.integers(min_value=1, max_value=30),
    temp_early=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    temp_mid=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    temp_late=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    mistake_early=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    mistake_mid=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    mistake_late=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_property_round_based_parameter_consistency(
    round_num, temp_early, temp_mid, temp_late, 
    mistake_early, mistake_mid, mistake_late
):
    """
    Property 12: Round-Based Parameter Consistency
    
    For any round number, the temperature and mistake rate returned should match 
    the configured values for the appropriate round range (early: 1-5, mid: 6-15, late: 16+).
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
    """
    # Create config with the generated parameters
    config = VariabilityConfig(
        temperature_early_rounds=temp_early,
        temperature_mid_rounds=temp_mid,
        temperature_late_rounds=temp_late,
        mistake_rate_early=mistake_early,
        mistake_rate_mid=mistake_mid,
        mistake_rate_late=mistake_late
    )
    
    # Get temperature and mistake rate for the round
    temperature = config.get_temperature_for_round(round_num)
    mistake_rate = config.get_mistake_rate_for_round(round_num)
    
    # Property: Temperature should match the appropriate round range
    if round_num <= 5:
        assert temperature == temp_early, \
            f"Round {round_num} should use early temperature {temp_early}, got {temperature}"
        assert mistake_rate == mistake_early, \
            f"Round {round_num} should use early mistake rate {mistake_early}, got {mistake_rate}"
    elif round_num <= 15:
        assert temperature == temp_mid, \
            f"Round {round_num} should use mid temperature {temp_mid}, got {temperature}"
        assert mistake_rate == mistake_mid, \
            f"Round {round_num} should use mid mistake rate {mistake_mid}, got {mistake_rate}"
    else:
        assert temperature == temp_late, \
            f"Round {round_num} should use late temperature {temp_late}, got {temperature}"
        assert mistake_rate == mistake_late, \
            f"Round {round_num} should use late mistake rate {mistake_late}, got {mistake_rate}"


def test_round_based_parameter_boundaries():
    """
    Unit test: Test boundary conditions for round-based parameter selection.
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
    """
    config = VariabilityConfig(
        temperature_early_rounds=0.3,
        temperature_mid_rounds=0.7,
        temperature_late_rounds=1.2,
        mistake_rate_early=0.05,
        mistake_rate_mid=0.10,
        mistake_rate_late=0.15
    )
    
    # Test early rounds (1-5)
    assert config.get_temperature_for_round(1) == 0.3
    assert config.get_temperature_for_round(5) == 0.3
    assert config.get_mistake_rate_for_round(1) == 0.05
    assert config.get_mistake_rate_for_round(5) == 0.05
    
    # Test mid rounds (6-15)
    assert config.get_temperature_for_round(6) == 0.7
    assert config.get_temperature_for_round(15) == 0.7
    assert config.get_mistake_rate_for_round(6) == 0.10
    assert config.get_mistake_rate_for_round(15) == 0.10
    
    # Test late rounds (16+)
    assert config.get_temperature_for_round(16) == 1.2
    assert config.get_temperature_for_round(20) == 1.2
    assert config.get_mistake_rate_for_round(16) == 0.15
    assert config.get_mistake_rate_for_round(25) == 0.15


# Property 13: Configuration Serialization Round-Trip
# Validates: Requirements 8.3
@given(
    variability_enabled=st.booleans(),
    random_seed=st.one_of(st.none(), st.integers(min_value=0, max_value=1000000)),
    temp_early=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    temp_mid=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    temp_late=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    mistake_early=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    mistake_mid=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    mistake_late=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    top_n=st.integers(min_value=1, max_value=20),
)
def test_property_configuration_serialization_round_trip(
    variability_enabled, random_seed, temp_early, temp_mid, temp_late,
    mistake_early, mistake_mid, mistake_late, top_n
):
    """
    Property 13: Configuration Serialization Round-Trip
    
    For any valid VariabilityConfig object, serializing to JSON and then 
    deserializing should produce an equivalent configuration with all fields preserved.
    
    Validates: Requirements 8.3
    """
    # Create original config
    original_config = VariabilityConfig(
        variability_enabled=variability_enabled,
        random_seed=random_seed,
        temperature_early_rounds=temp_early,
        temperature_mid_rounds=temp_mid,
        temperature_late_rounds=temp_late,
        mistake_rate_early=mistake_early,
        mistake_rate_mid=mistake_mid,
        mistake_rate_late=mistake_late,
        top_n_candidates=top_n
    )
    
    # Serialize to dict
    config_dict = original_config.to_dict()
    
    # Deserialize from dict
    restored_config = VariabilityConfig.from_dict(config_dict)
    
    # Property: All fields should be preserved
    assert restored_config.variability_enabled == original_config.variability_enabled
    assert restored_config.random_seed == original_config.random_seed
    assert restored_config.temperature_early_rounds == original_config.temperature_early_rounds
    assert restored_config.temperature_mid_rounds == original_config.temperature_mid_rounds
    assert restored_config.temperature_late_rounds == original_config.temperature_late_rounds
    assert restored_config.mistake_rate_early == original_config.mistake_rate_early
    assert restored_config.mistake_rate_mid == original_config.mistake_rate_mid
    assert restored_config.mistake_rate_late == original_config.mistake_rate_late
    assert restored_config.top_n_candidates == original_config.top_n_candidates
    assert restored_config.suboptimal_range == original_config.suboptimal_range
    
    # Property: Strategy profiles should be preserved
    assert len(restored_config.strategy_profiles) == len(original_config.strategy_profiles)
    for name in original_config.strategy_profiles:
        assert name in restored_config.strategy_profiles
        original_strategy = original_config.strategy_profiles[name]
        restored_strategy = restored_config.strategy_profiles[name]
        assert restored_strategy.name == original_strategy.name
        assert restored_strategy.adp_weight == original_strategy.adp_weight
        assert restored_strategy.team_needs_weight == original_strategy.team_needs_weight


def test_configuration_file_round_trip(tmp_path):
    """
    Unit test: Test saving and loading configuration from file.
    
    Validates: Requirements 8.1, 8.2, 8.3
    """
    # Create a config
    original_config = VariabilityConfig(
        variability_enabled=True,
        random_seed=42,
        temperature_early_rounds=0.3,
        temperature_mid_rounds=0.7,
        temperature_late_rounds=1.2,
        top_n_candidates=5
    )
    
    # Save to file
    filepath = tmp_path / "test_config.json"
    original_config.save_to_file(str(filepath))
    
    # Load from file
    loaded_config = VariabilityConfig.load_from_file(str(filepath))
    
    # Verify all fields match
    assert loaded_config.variability_enabled == original_config.variability_enabled
    assert loaded_config.random_seed == original_config.random_seed
    assert loaded_config.temperature_early_rounds == original_config.temperature_early_rounds
    assert loaded_config.temperature_mid_rounds == original_config.temperature_mid_rounds
    assert loaded_config.temperature_late_rounds == original_config.temperature_late_rounds
    assert loaded_config.top_n_candidates == original_config.top_n_candidates


# Property 14: Configuration Validation
# Validates: Requirements 8.4
@given(
    temp_early=st.floats(min_value=-1.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    temp_mid=st.floats(min_value=-1.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    temp_late=st.floats(min_value=-1.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    mistake_early=st.floats(min_value=-0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    mistake_mid=st.floats(min_value=-0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    mistake_late=st.floats(min_value=-0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    top_n=st.integers(min_value=-5, max_value=25),
)
def test_property_configuration_validation(
    temp_early, temp_mid, temp_late,
    mistake_early, mistake_mid, mistake_late, top_n
):
    """
    Property 14: Configuration Validation
    
    For any configuration loaded from file, if any parameter is outside acceptable 
    ranges, the validation should fail and report the specific errors.
    
    Validates: Requirements 8.4
    """
    # Create config with potentially invalid parameters
    config = VariabilityConfig(
        temperature_early_rounds=temp_early,
        temperature_mid_rounds=temp_mid,
        temperature_late_rounds=temp_late,
        mistake_rate_early=mistake_early,
        mistake_rate_mid=mistake_mid,
        mistake_rate_late=mistake_late,
        top_n_candidates=top_n
    )
    
    errors = config.validate()
    
    # Property: Temperature values outside [0.0, 2.0] should be flagged
    if not (0.0 <= temp_early <= 2.0):
        assert any("temperature_early_rounds" in error for error in errors), \
            f"Invalid temperature_early_rounds {temp_early} not detected"
    else:
        assert not any("temperature_early_rounds" in error for error in errors), \
            f"Valid temperature_early_rounds {temp_early} incorrectly flagged"
    
    if not (0.0 <= temp_mid <= 2.0):
        assert any("temperature_mid_rounds" in error for error in errors), \
            f"Invalid temperature_mid_rounds {temp_mid} not detected"
    else:
        assert not any("temperature_mid_rounds" in error for error in errors), \
            f"Valid temperature_mid_rounds {temp_mid} incorrectly flagged"
    
    if not (0.0 <= temp_late <= 2.0):
        assert any("temperature_late_rounds" in error for error in errors), \
            f"Invalid temperature_late_rounds {temp_late} not detected"
    else:
        assert not any("temperature_late_rounds" in error for error in errors), \
            f"Valid temperature_late_rounds {temp_late} incorrectly flagged"
    
    # Property: Mistake rates outside [0.0, 1.0] should be flagged
    if not (0.0 <= mistake_early <= 1.0):
        assert any("mistake_rate_early" in error for error in errors), \
            f"Invalid mistake_rate_early {mistake_early} not detected"
    else:
        assert not any("mistake_rate_early" in error for error in errors), \
            f"Valid mistake_rate_early {mistake_early} incorrectly flagged"
    
    if not (0.0 <= mistake_mid <= 1.0):
        assert any("mistake_rate_mid" in error for error in errors), \
            f"Invalid mistake_rate_mid {mistake_mid} not detected"
    else:
        assert not any("mistake_rate_mid" in error for error in errors), \
            f"Valid mistake_rate_mid {mistake_mid} incorrectly flagged"
    
    if not (0.0 <= mistake_late <= 1.0):
        assert any("mistake_rate_late" in error for error in errors), \
            f"Invalid mistake_rate_late {mistake_late} not detected"
    else:
        assert not any("mistake_rate_late" in error for error in errors), \
            f"Valid mistake_rate_late {mistake_late} incorrectly flagged"
    
    # Property: top_n_candidates < 1 should be flagged
    if top_n < 1:
        assert any("top_n_candidates" in error for error in errors), \
            f"Invalid top_n_candidates {top_n} not detected"
    else:
        assert not any("top_n_candidates" in error for error in errors), \
            f"Valid top_n_candidates {top_n} incorrectly flagged"


def test_configuration_validation_edge_cases():
    """
    Unit test: Test edge cases for configuration validation.
    
    Validates: Requirements 8.4
    """
    # Test invalid suboptimal_range
    config = VariabilityConfig(suboptimal_range=(10, 5))  # min > max
    errors = config.validate()
    assert any("suboptimal_range[0] must be less than" in error for error in errors)
    
    # Test invalid suboptimal_range with negative values
    config = VariabilityConfig(suboptimal_range=(-1, 10))
    errors = config.validate()
    assert any("suboptimal_range values must be at least 1" in error for error in errors)
    
    # Test invalid team strategy assignment
    config = VariabilityConfig(team_strategies={"Team A": "non_existent_strategy"})
    errors = config.validate()
    assert any("non-existent strategy" in error for error in errors)
    
    # Test valid configuration
    config = VariabilityConfig()
    errors = config.validate()
    assert len(errors) == 0, f"Default config should be valid, got errors: {errors}"
