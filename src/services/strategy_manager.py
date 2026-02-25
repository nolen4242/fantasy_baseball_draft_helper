"""
Strategy management for auto-draft variability.

This module provides the StrategyManager class that handles strategy assignment
to teams and applies strategy-specific modifications to scoring configurations.
"""

from typing import Dict, List
import numpy as np

from src.services.variability_config import VariabilityConfig, StrategyProfile, STRATEGY_PROFILES
from src.services.scoring_config import ScoringConfig


class StrategyManager:
    """Manages strategy assignment and application for auto-drafted teams."""
    
    def __init__(self, config: VariabilityConfig, random_state: np.random.RandomState):
        """
        Initialize the StrategyManager.
        
        Args:
            config: VariabilityConfig containing strategy profiles and assignments
            random_state: NumPy random state for reproducible randomness
        """
        self.config = config
        self.random_state = random_state
        self.team_strategies: Dict[str, StrategyProfile] = {}
    
    def assign_strategies_to_teams(self, team_names: List[str]):
        """
        Randomly assign strategies to teams at the start of a draft.
        
        Args:
            team_names: List of team names to assign strategies to
        """
        available_strategies = list(self.config.strategy_profiles.keys())
        
        for team_name in team_names:
            # Check if team already has assigned strategy in config
            if team_name in self.config.team_strategies:
                strategy_name = self.config.team_strategies[team_name]
            else:
                # Randomly assign a strategy
                strategy_name = self.random_state.choice(available_strategies)
            
            self.team_strategies[team_name] = self.config.strategy_profiles[strategy_name]
    
    def get_strategy_for_team(self, team_name: str) -> StrategyProfile:
        """
        Get the strategy profile for a specific team.
        
        Args:
            team_name: Name of the team
            
        Returns:
            StrategyProfile for the team, or balanced strategy if not found
        """
        return self.team_strategies.get(team_name, STRATEGY_PROFILES['balanced'])
    
    def apply_strategy_to_scoring_config(
        self, 
        base_config: ScoringConfig, 
        strategy: StrategyProfile
    ) -> ScoringConfig:
        """
        Create a modified scoring config based on strategy preferences.
        
        Args:
            base_config: Base ScoringConfig to modify
            strategy: StrategyProfile to apply
            
        Returns:
            Modified ScoringConfig with strategy-specific adjustments
        """
        # Create a copy of the base config
        modified_config = ScoringConfig.from_dict(base_config.to_dict())
        
        # Apply strategy weights
        modified_config.autodraft_adp_weight = strategy.adp_weight
        modified_config.autodraft_team_needs_weight = strategy.team_needs_weight
        modified_config.autodraft_position_scarcity_weight = strategy.position_scarcity_weight
        
        # Apply position preferences by modifying position scarcity bonuses
        if strategy.hitter_preference != 1.0:
            # Adjust hitter-related bonuses
            modified_config.hitter_lineup_bonus_0_2 *= strategy.hitter_preference
            modified_config.hitter_lineup_bonus_3_5 *= strategy.hitter_preference
            modified_config.hitter_lineup_bonus_6_8 *= strategy.hitter_preference
        
        if strategy.pitcher_preference != 1.0:
            # Adjust pitcher-related bonuses
            modified_config.ip_accumulation_base_0_20 *= strategy.pitcher_preference
            modified_config.ip_accumulation_base_20_50 *= strategy.pitcher_preference
            modified_config.ip_accumulation_base_50_80 *= strategy.pitcher_preference
            modified_config.ip_accumulation_base_80_100 *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_high *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_moderate *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_low *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_deep *= strategy.pitcher_preference
        
        # Apply specific position preferences
        if strategy.catcher_preference != 1.0:
            modified_config.elite_position_scarce *= strategy.catcher_preference
        
        if strategy.shortstop_preference != 1.0:
            modified_config.elite_position_moderate *= strategy.shortstop_preference
        
        if strategy.outfield_preference != 1.0:
            modified_config.mid_tier_position *= strategy.outfield_preference
        
        # Apply category preferences
        modified_config.category_weight_hr *= strategy.power_preference
        modified_config.category_weight_rbi *= strategy.power_preference
        modified_config.category_weight_sb *= strategy.speed_preference
        modified_config.category_weight_obp *= strategy.average_preference
        modified_config.category_weight_k *= strategy.strikeout_preference
        modified_config.category_weight_era *= strategy.ratio_preference
        modified_config.category_weight_whip *= strategy.ratio_preference
        modified_config.category_weight_wins *= strategy.wins_preference
        modified_config.category_weight_qs *= strategy.wins_preference
        modified_config.category_weight_saves *= strategy.saves_preference
        modified_config.category_weight_holds *= strategy.saves_preference
        
        return modified_config
