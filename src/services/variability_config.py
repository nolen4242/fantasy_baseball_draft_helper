"""
Configuration classes for auto-draft variability.

This module provides data structures for managing variability in the auto-draft
system, including strategy profiles and variability configuration.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path


@dataclass
class StrategyProfile:
    """Defines a drafter strategy with custom scoring weights."""
    
    name: str
    description: str
    
    # Auto-draft scoring weights (must sum to 1.0)
    adp_weight: float = 0.60
    team_needs_weight: float = 0.30
    position_scarcity_weight: float = 0.10
    
    # Position preferences (multipliers applied to position scores)
    hitter_preference: float = 1.0
    pitcher_preference: float = 1.0
    
    # Specific position preferences
    catcher_preference: float = 1.0
    shortstop_preference: float = 1.0
    outfield_preference: float = 1.0
    
    # Category preferences (multipliers for category targeting)
    power_preference: float = 1.0      # HR, RBI
    speed_preference: float = 1.0      # SB
    average_preference: float = 1.0    # OBP
    strikeout_preference: float = 1.0  # K
    ratio_preference: float = 1.0      # ERA, WHIP
    wins_preference: float = 1.0       # W, QS
    saves_preference: float = 1.0      # SV, HLD
    
    def validate(self) -> List[str]:
        """Validate that weights sum to 1.0 and are in valid ranges."""
        errors = []
        
        # Check weight sum
        weight_sum = self.adp_weight + self.team_needs_weight + self.position_scarcity_weight
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"Weights sum to {weight_sum:.2f}, must sum to 1.0")
        
        # Check individual weights are in valid range
        if not (0.0 <= self.adp_weight <= 1.0):
            errors.append("adp_weight must be between 0.0 and 1.0")
        if not (0.0 <= self.team_needs_weight <= 1.0):
            errors.append("team_needs_weight must be between 0.0 and 1.0")
        if not (0.0 <= self.position_scarcity_weight <= 1.0):
            errors.append("position_scarcity_weight must be between 0.0 and 1.0")
        
        # Check all preferences are non-negative
        preference_fields = [
            'hitter_preference', 'pitcher_preference', 'catcher_preference',
            'shortstop_preference', 'outfield_preference', 'power_preference',
            'speed_preference', 'average_preference', 'strikeout_preference',
            'ratio_preference', 'wins_preference', 'saves_preference'
        ]
        
        for field_name in preference_fields:
            value = getattr(self, field_name)
            if value < 0:
                errors.append(f"{field_name} must be non-negative")
        
        return errors
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StrategyProfile':
        """Create from dictionary."""
        return cls(**data)


# Predefined strategy profiles
STRATEGY_PROFILES = {
    'balanced': StrategyProfile(
        name='balanced',
        description='Balanced approach following ADP with moderate team needs consideration',
        adp_weight=0.60,
        team_needs_weight=0.30,
        position_scarcity_weight=0.10
    ),
    
    'aggressive_hitters': StrategyProfile(
        name='aggressive_hitters',
        description='Prioritizes elite hitters and offensive categories',
        adp_weight=0.50,
        team_needs_weight=0.35,
        position_scarcity_weight=0.15,
        hitter_preference=1.3,
        pitcher_preference=0.7,
        power_preference=1.2,
        speed_preference=1.1
    ),
    
    'pitcher_heavy': StrategyProfile(
        name='pitcher_heavy',
        description='Emphasizes pitching depth and ratio categories',
        adp_weight=0.55,
        team_needs_weight=0.30,
        position_scarcity_weight=0.15,
        hitter_preference=0.8,
        pitcher_preference=1.4,
        strikeout_preference=1.2,
        ratio_preference=1.3,
        wins_preference=1.1
    ),
    
    'value_focused': StrategyProfile(
        name='value_focused',
        description='Strictly follows ADP value, less concerned with team needs',
        adp_weight=0.80,
        team_needs_weight=0.15,
        position_scarcity_weight=0.05
    ),
    
    'position_scarcity': StrategyProfile(
        name='position_scarcity',
        description='Prioritizes scarce positions like catcher and shortstop',
        adp_weight=0.45,
        team_needs_weight=0.30,
        position_scarcity_weight=0.25,
        catcher_preference=1.4,
        shortstop_preference=1.3
    )
}


@dataclass
class VariabilityConfig:
    """Configuration for auto-draft variability."""
    
    # Global settings
    variability_enabled: bool = False
    random_seed: Optional[int] = None
    
    # Temperature settings (by round range)
    temperature_early_rounds: float = 0.3  # Rounds 1-5
    temperature_mid_rounds: float = 0.7    # Rounds 6-15
    temperature_late_rounds: float = 1.2   # Rounds 16+
    
    # Mistake rate settings (by round range)
    mistake_rate_early: float = 0.05   # 5% in rounds 1-5
    mistake_rate_mid: float = 0.10     # 10% in rounds 6-15
    mistake_rate_late: float = 0.15    # 15% in rounds 16+
    
    # Selection settings
    top_n_candidates: int = 5          # Number of top candidates to sample from
    suboptimal_range: Tuple[int, int] = (6, 15)  # Rank range for suboptimal picks
    
    # Strategy profiles
    strategy_profiles: Dict[str, StrategyProfile] = field(default_factory=lambda: {
        name: profile for name, profile in STRATEGY_PROFILES.items()
    })
    
    # Team strategy assignments
    team_strategies: Dict[str, str] = field(default_factory=dict)
    
    def get_temperature_for_round(self, round_num: int) -> float:
        """Get temperature value for a specific round."""
        if round_num <= 5:
            return self.temperature_early_rounds
        elif round_num <= 15:
            return self.temperature_mid_rounds
        else:
            return self.temperature_late_rounds
    
    def get_mistake_rate_for_round(self, round_num: int) -> float:
        """Get mistake rate for a specific round."""
        if round_num <= 5:
            return self.mistake_rate_early
        elif round_num <= 15:
            return self.mistake_rate_mid
        else:
            return self.mistake_rate_late
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert strategy profiles to dict format
        data['strategy_profiles'] = {
            name: profile.to_dict() for name, profile in self.strategy_profiles.items()
        }
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VariabilityConfig':
        """Create from dictionary."""
        # Convert strategy profiles from dict format
        if 'strategy_profiles' in data:
            data['strategy_profiles'] = {
                name: StrategyProfile.from_dict(profile_data)
                for name, profile_data in data['strategy_profiles'].items()
            }
        
        # Handle tuple conversion for suboptimal_range
        if 'suboptimal_range' in data and isinstance(data['suboptimal_range'], list):
            data['suboptimal_range'] = tuple(data['suboptimal_range'])
        
        return cls(**data)
    
    def save_to_file(self, filepath: str):
        """Save configuration to JSON file."""
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'VariabilityConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """Validate configuration values. Returns list of errors."""
        errors = []
        
        # Validate temperature ranges
        if not (0.0 <= self.temperature_early_rounds <= 2.0):
            errors.append("temperature_early_rounds must be between 0.0 and 2.0")
        if not (0.0 <= self.temperature_mid_rounds <= 2.0):
            errors.append("temperature_mid_rounds must be between 0.0 and 2.0")
        if not (0.0 <= self.temperature_late_rounds <= 2.0):
            errors.append("temperature_late_rounds must be between 0.0 and 2.0")
        
        # Validate mistake rates
        if not (0.0 <= self.mistake_rate_early <= 1.0):
            errors.append("mistake_rate_early must be between 0.0 and 1.0")
        if not (0.0 <= self.mistake_rate_mid <= 1.0):
            errors.append("mistake_rate_mid must be between 0.0 and 1.0")
        if not (0.0 <= self.mistake_rate_late <= 1.0):
            errors.append("mistake_rate_late must be between 0.0 and 1.0")
        
        # Validate selection settings
        if self.top_n_candidates < 1:
            errors.append("top_n_candidates must be at least 1")
        
        if len(self.suboptimal_range) != 2:
            errors.append("suboptimal_range must be a tuple of 2 integers")
        elif self.suboptimal_range[0] >= self.suboptimal_range[1]:
            errors.append("suboptimal_range[0] must be less than suboptimal_range[1]")
        elif self.suboptimal_range[0] < 1:
            errors.append("suboptimal_range values must be at least 1")
        
        # Validate strategy profiles
        for name, profile in self.strategy_profiles.items():
            profile_errors = profile.validate()
            for error in profile_errors:
                errors.append(f"Strategy '{name}': {error}")
        
        # Validate team strategy assignments
        for team_name, strategy_name in self.team_strategies.items():
            if strategy_name not in self.strategy_profiles:
                errors.append(f"Team '{team_name}' assigned non-existent strategy '{strategy_name}'")
        
        return errors
