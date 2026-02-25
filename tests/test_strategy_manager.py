"""
Property-based tests for strategy manager.

Feature: auto-draft-variability
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, assume

from src.services.strategy_manager import StrategyManager
from src.services.variability_config import VariabilityConfig, StrategyProfile, STRATEGY_PROFILES
from src.services.scoring_config import ScoringConfig


# Property 8: Strategy Assignment Completeness
# Validates: Requirements 2.2
@given(
    num_teams=st.integers(min_value=1, max_value=20),
    random_seed=st.integers(min_value=0, max_value=1000000),
)
def test_property_strategy_assignment_completeness(num_teams, random_seed):
    """
    Property 8: Strategy Assignment Completeness
    
    For any list of team names, after strategy assignment, every team should 
    have an assigned strategy profile.
    
    Validates: Requirements 2.2
    """
    # Create team names
    team_names = [f"Team_{i}" for i in range(num_teams)]
    
    # Create config and random state
    config = VariabilityConfig()
    random_state = np.random.RandomState(random_seed)
    
    # Create strategy manager
    manager = StrategyManager(config, random_state)
    
    # Assign strategies
    manager.assign_strategies_to_teams(team_names)
    
    # Property: Every team should have an assigned strategy
    for team_name in team_names:
        strategy = manager.get_strategy_for_team(team_name)
        assert strategy is not None, f"Team '{team_name}' has no assigned strategy"
        assert isinstance(strategy, StrategyProfile), \
            f"Team '{team_name}' strategy is not a StrategyProfile"
        assert strategy.name in STRATEGY_PROFILES, \
            f"Team '{team_name}' has invalid strategy '{strategy.name}'"


@given(
    num_teams=st.integers(min_value=1, max_value=20),
    random_seed=st.integers(min_value=0, max_value=1000000),
)
def test_property_strategy_assignment_uses_available_strategies(num_teams, random_seed):
    """
    Property 8 (extended): Strategy Assignment Uses Available Strategies
    
    For any list of team names, all assigned strategies should come from the 
    available strategy profiles in the config.
    
    Validates: Requirements 2.2
    """
    # Create team names
    team_names = [f"Team_{i}" for i in range(num_teams)]
    
    # Create config with default strategies
    config = VariabilityConfig()
    random_state = np.random.RandomState(random_seed)
    
    # Create strategy manager
    manager = StrategyManager(config, random_state)
    
    # Assign strategies
    manager.assign_strategies_to_teams(team_names)
    
    # Property: All assigned strategies should be from available profiles
    available_strategy_names = set(config.strategy_profiles.keys())
    
    for team_name in team_names:
        strategy = manager.get_strategy_for_team(team_name)
        assert strategy.name in available_strategy_names, \
            f"Team '{team_name}' assigned unavailable strategy '{strategy.name}'"


def test_strategy_assignment_respects_predefined_assignments():
    """
    Unit test: Strategy assignment should respect predefined team assignments.
    
    Validates: Requirements 2.2
    """
    # Create config with predefined team assignments
    config = VariabilityConfig(
        team_strategies={
            "Team_0": "aggressive_hitters",
            "Team_1": "pitcher_heavy",
        }
    )
    random_state = np.random.RandomState(42)
    
    # Create strategy manager
    manager = StrategyManager(config, random_state)
    
    # Assign strategies to teams
    team_names = ["Team_0", "Team_1", "Team_2"]
    manager.assign_strategies_to_teams(team_names)
    
    # Verify predefined assignments are respected
    assert manager.get_strategy_for_team("Team_0").name == "aggressive_hitters"
    assert manager.get_strategy_for_team("Team_1").name == "pitcher_heavy"
    
    # Team_2 should get a random assignment (any valid strategy)
    team_2_strategy = manager.get_strategy_for_team("Team_2")
    assert team_2_strategy.name in STRATEGY_PROFILES


def test_strategy_assignment_fallback_to_balanced():
    """
    Unit test: Getting strategy for unknown team should return balanced strategy.
    
    Validates: Requirements 2.2
    """
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    
    manager = StrategyManager(config, random_state)
    
    # Get strategy for team that was never assigned
    strategy = manager.get_strategy_for_team("Unknown_Team")
    
    # Should return balanced strategy as fallback
    assert strategy.name == "balanced"


# Property 9: Strategy Application Consistency
# Validates: Requirements 2.3
@given(
    random_seed=st.integers(min_value=0, max_value=1000000),
)
def test_property_strategy_application_consistency(random_seed):
    """
    Property 9: Strategy Application Consistency
    
    For any base ScoringConfig and StrategyProfile, applying the strategy should 
    modify the autodraft weights to match the strategy's weights, and should scale 
    position/category preferences by the strategy's multipliers.
    
    Validates: Requirements 2.3
    """
    # Create base config
    base_config = ScoringConfig()
    
    # Store original values
    original_adp_weight = base_config.autodraft_adp_weight
    original_team_needs_weight = base_config.autodraft_team_needs_weight
    original_position_scarcity_weight = base_config.autodraft_position_scarcity_weight
    original_hitter_bonus = base_config.hitter_lineup_bonus_0_2
    original_pitcher_bonus = base_config.ip_accumulation_base_0_20
    original_hr_weight = base_config.category_weight_hr
    original_sb_weight = base_config.category_weight_sb
    
    # Test each predefined strategy
    for strategy_name, strategy in STRATEGY_PROFILES.items():
        config = VariabilityConfig()
        random_state = np.random.RandomState(random_seed)
        manager = StrategyManager(config, random_state)
        
        # Apply strategy to base config
        modified_config = manager.apply_strategy_to_scoring_config(base_config, strategy)
        
        # Property: Autodraft weights should match strategy weights
        assert modified_config.autodraft_adp_weight == strategy.adp_weight, \
            f"Strategy '{strategy_name}' adp_weight not applied correctly"
        assert modified_config.autodraft_team_needs_weight == strategy.team_needs_weight, \
            f"Strategy '{strategy_name}' team_needs_weight not applied correctly"
        assert modified_config.autodraft_position_scarcity_weight == strategy.position_scarcity_weight, \
            f"Strategy '{strategy_name}' position_scarcity_weight not applied correctly"
        
        # Property: Position preferences should scale bonuses
        if strategy.hitter_preference != 1.0:
            expected_hitter_bonus = original_hitter_bonus * strategy.hitter_preference
            assert abs(modified_config.hitter_lineup_bonus_0_2 - expected_hitter_bonus) < 0.01, \
                f"Strategy '{strategy_name}' hitter_preference not applied correctly"
        
        if strategy.pitcher_preference != 1.0:
            expected_pitcher_bonus = original_pitcher_bonus * strategy.pitcher_preference
            assert abs(modified_config.ip_accumulation_base_0_20 - expected_pitcher_bonus) < 0.01, \
                f"Strategy '{strategy_name}' pitcher_preference not applied correctly"
        
        # Property: Category preferences should scale category weights
        if strategy.power_preference != 1.0:
            expected_hr_weight = original_hr_weight * strategy.power_preference
            assert abs(modified_config.category_weight_hr - expected_hr_weight) < 0.01, \
                f"Strategy '{strategy_name}' power_preference not applied to HR weight"
        
        if strategy.speed_preference != 1.0:
            expected_sb_weight = original_sb_weight * strategy.speed_preference
            assert abs(modified_config.category_weight_sb - expected_sb_weight) < 0.01, \
                f"Strategy '{strategy_name}' speed_preference not applied to SB weight"


@given(
    hitter_pref=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    pitcher_pref=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_property_strategy_application_preserves_base_config(
    hitter_pref, pitcher_pref
):
    """
    Property 9 (extended): Strategy Application Preserves Base Config
    
    For any base ScoringConfig and StrategyProfile, applying the strategy should 
    not modify the original base config (immutability).
    
    Validates: Requirements 2.3
    """
    # Use fixed valid weights that sum to 1.0
    adp_weight = 0.6
    team_needs_weight = 0.3
    position_scarcity_weight = 0.1
    
    # Create base config
    base_config = ScoringConfig()
    
    # Store original values
    original_adp_weight = base_config.autodraft_adp_weight
    original_hitter_bonus = base_config.hitter_lineup_bonus_0_2
    
    # Create custom strategy
    strategy = StrategyProfile(
        name="custom",
        description="Custom strategy",
        adp_weight=adp_weight,
        team_needs_weight=team_needs_weight,
        position_scarcity_weight=position_scarcity_weight,
        hitter_preference=hitter_pref,
        pitcher_preference=pitcher_pref
    )
    
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    manager = StrategyManager(config, random_state)
    
    # Apply strategy
    modified_config = manager.apply_strategy_to_scoring_config(base_config, strategy)
    
    # Property: Base config should remain unchanged
    assert base_config.autodraft_adp_weight == original_adp_weight, \
        "Base config was modified (adp_weight changed)"
    assert base_config.hitter_lineup_bonus_0_2 == original_hitter_bonus, \
        "Base config was modified (hitter_lineup_bonus_0_2 changed)"
    
    # Property: Modified config should have strategy values
    assert modified_config.autodraft_adp_weight == strategy.adp_weight, \
        "Modified config does not have strategy adp_weight"


def test_strategy_application_specific_positions():
    """
    Unit test: Strategy application should correctly apply specific position preferences.
    
    Validates: Requirements 2.3, 5.1, 5.2, 5.3, 5.4, 5.5
    """
    base_config = ScoringConfig()
    
    # Test position_scarcity strategy with catcher and shortstop preferences
    strategy = STRATEGY_PROFILES['position_scarcity']
    
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    manager = StrategyManager(config, random_state)
    
    modified_config = manager.apply_strategy_to_scoring_config(base_config, strategy)
    
    # Verify catcher preference is applied
    expected_catcher_bonus = base_config.elite_position_scarce * strategy.catcher_preference
    assert abs(modified_config.elite_position_scarce - expected_catcher_bonus) < 0.01
    
    # Verify shortstop preference is applied
    expected_ss_bonus = base_config.elite_position_moderate * strategy.shortstop_preference
    assert abs(modified_config.elite_position_moderate - expected_ss_bonus) < 0.01


def test_strategy_application_category_preferences():
    """
    Unit test: Strategy application should correctly apply category preferences.
    
    Validates: Requirements 2.3, 5.2, 5.3
    """
    base_config = ScoringConfig()
    
    # Test aggressive_hitters strategy with power and speed preferences
    strategy = STRATEGY_PROFILES['aggressive_hitters']
    
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    manager = StrategyManager(config, random_state)
    
    modified_config = manager.apply_strategy_to_scoring_config(base_config, strategy)
    
    # Verify power preference is applied to HR and RBI
    expected_hr_weight = base_config.category_weight_hr * strategy.power_preference
    expected_rbi_weight = base_config.category_weight_rbi * strategy.power_preference
    assert abs(modified_config.category_weight_hr - expected_hr_weight) < 0.01
    assert abs(modified_config.category_weight_rbi - expected_rbi_weight) < 0.01
    
    # Verify speed preference is applied to SB
    expected_sb_weight = base_config.category_weight_sb * strategy.speed_preference
    assert abs(modified_config.category_weight_sb - expected_sb_weight) < 0.01


def test_strategy_application_pitcher_heavy():
    """
    Unit test: Pitcher heavy strategy should increase pitcher-related bonuses.
    
    Validates: Requirements 2.3, 5.3
    """
    base_config = ScoringConfig()
    strategy = STRATEGY_PROFILES['pitcher_heavy']
    
    config = VariabilityConfig()
    random_state = np.random.RandomState(42)
    manager = StrategyManager(config, random_state)
    
    modified_config = manager.apply_strategy_to_scoring_config(base_config, strategy)
    
    # Verify pitcher preference increases IP accumulation bonuses
    assert modified_config.ip_accumulation_base_0_20 > base_config.ip_accumulation_base_0_20
    assert modified_config.ip_accumulation_base_20_50 > base_config.ip_accumulation_base_20_50
    
    # Verify pitcher scarcity bonuses are increased
    assert modified_config.pitcher_scarcity_high > base_config.pitcher_scarcity_high
    assert modified_config.pitcher_scarcity_moderate > base_config.pitcher_scarcity_moderate
    
    # Verify ratio and strikeout preferences are applied
    assert modified_config.category_weight_era > base_config.category_weight_era
    assert modified_config.category_weight_whip > base_config.category_weight_whip
    assert modified_config.category_weight_k > base_config.category_weight_k
