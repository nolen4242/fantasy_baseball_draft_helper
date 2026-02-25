"""
Centralized configuration for recommendation scoring.

This module provides the ScoringConfig dataclass that centralizes all scoring
weights and parameters used by the recommendation engine.
"""

from dataclasses import dataclass, asdict
from typing import List
import json
from pathlib import Path


@dataclass
class ScoringConfig:
    """Centralized configuration for recommendation scoring."""
    
    # Primary factors
    standings_multiplier: float = 30.0
    
    # Roster balance - IP accumulation
    ip_accumulation_base_0_20: float = 200.0
    ip_accumulation_base_20_50: float = 150.0
    ip_accumulation_base_50_80: float = 100.0
    ip_accumulation_base_80_100: float = 50.0
    ip_contribution_per_ip: float = 0.3
    
    # Roster balance - Hitter lineup
    hitter_lineup_bonus_0_2: float = 260.0
    hitter_lineup_bonus_3_5: float = 150.0
    hitter_lineup_bonus_6_8: float = 75.0
    
    # ML model
    ml_multiplier: float = 3.0
    
    # Future availability
    availability_bonus_0_10: float = 120.0
    availability_bonus_10_30: float = 80.0
    availability_bonus_30_50: float = 30.0
    availability_penalty_50_70: float = -30.0
    availability_penalty_70_85: float = -80.0
    availability_penalty_85_100: float = -150.0
    
    # Team needs
    position_need_bonus: float = 80.0
    redundant_position_penalty: float = -200.0
    behind_pace_bonus: float = 40.0
    no_pitchers_bonus: float = 60.0
    enough_pitchers_penalty: float = -100.0
    
    # Position scarcity
    elite_position_scarce: float = 150.0
    elite_position_moderate: float = 100.0
    mid_tier_position: float = 50.0
    pitcher_scarcity_high: float = 50.0
    pitcher_scarcity_moderate: float = 35.0
    pitcher_scarcity_low: float = 25.0
    pitcher_scarcity_deep: float = 15.0
    
    # Category targeting (per-category weights)
    category_weight_hr: float = 2.5
    category_weight_r: float = 0.6
    category_weight_rbi: float = 0.6
    category_weight_sb: float = 3.5
    category_weight_obp: float = 500.0
    category_weight_k: float = 0.1
    category_weight_era: float = 50.0
    category_weight_whip: float = 50.0
    category_weight_wins: float = 2.0
    category_weight_qs: float = 2.0
    category_weight_saves: float = 3.0
    category_weight_holds: float = 1.5
    
    # Relative advantage
    relative_advantage_multiplier: float = 50.0
    opponent_strategy_bonus: float = 30.0
    blocking_bonus_per_opponent: float = 15.0
    
    # Risk assessment
    injury_risk_penalty: float = -30.0
    age_decline_penalty: float = -20.0
    sample_size_penalty: float = -15.0
    
    # Fallback weights (when ML unavailable) - should sum to ~1.0
    fallback_adp_weight: float = 0.40
    fallback_team_needs_weight: float = 0.25
    fallback_position_scarcity_weight: float = 0.15
    fallback_category_targeting_weight: float = 0.10
    fallback_relative_advantage_weight: float = 0.05
    fallback_risk_weight: float = 0.05
    
    # Auto-draft weights (simplified)
    autodraft_adp_weight: float = 0.60
    autodraft_team_needs_weight: float = 0.30
    autodraft_position_scarcity_weight: float = 0.10
    
    # Metadata
    profile_name: str = "default"
    description: str = "Default balanced scoring"
    version: str = "1.0"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ScoringConfig':
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'ScoringConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def save_to_file(self, filepath: str):
        """Save configuration to JSON file."""
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def validate(self) -> List[str]:
        """Validate configuration values. Returns list of errors."""
        errors = []
        
        # Check for negative values where they shouldn't be
        if self.standings_multiplier < 0:
            errors.append("standings_multiplier must be positive")
        if self.ml_multiplier < 0:
            errors.append("ml_multiplier must be positive")
        
        # Check for reasonable ranges
        if self.ip_accumulation_base_0_20 < 0 or self.ip_accumulation_base_0_20 > 500:
            errors.append("ip_accumulation_base_0_20 should be 0-500")
        
        # Fallback weights should sum to ~1.0
        fallback_sum = (
            self.fallback_adp_weight +
            self.fallback_team_needs_weight +
            self.fallback_position_scarcity_weight +
            self.fallback_category_targeting_weight +
            self.fallback_relative_advantage_weight +
            self.fallback_risk_weight
        )
        if abs(fallback_sum - 1.0) > 0.1:
            errors.append(f"Fallback weights sum to {fallback_sum:.2f}, should be ~1.0")
        
        # Auto-draft weights should sum to ~1.0
        autodraft_sum = (
            self.autodraft_adp_weight +
            self.autodraft_team_needs_weight +
            self.autodraft_position_scarcity_weight
        )
        if abs(autodraft_sum - 1.0) > 0.1:
            errors.append(f"Auto-draft weights sum to {autodraft_sum:.2f}, should be ~1.0")
        
        return errors
