"""
Configuration manager for scoring profiles.

This module provides the ConfigManager class that manages loading, saving,
and switching between different scoring configuration profiles.
"""

from pathlib import Path
from typing import Dict, List
from src.services.scoring_config import ScoringConfig


class ConfigManager:
    """Manages scoring configuration profiles."""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the ConfigManager.
        
        Args:
            config_dir: Directory to store config files. If None, uses default location.
        """
        if config_dir is None:
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config" / "scoring"
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_config: ScoringConfig = ScoringConfig()
        self.profiles: Dict[str, ScoringConfig] = {}
        
        # Load default profiles
        self._load_default_profiles()
    
    def _load_default_profiles(self):
        """Load built-in default profiles."""
        # Default balanced profile
        self.profiles['default'] = ScoringConfig(
            profile_name='default',
            description='Balanced scoring for most situations'
        )
        
        # Aggressive profile (prioritize value over safety)
        self.profiles['aggressive'] = ScoringConfig(
            profile_name='aggressive',
            description='Aggressive value-seeking strategy',
            availability_penalty_85_100=-50.0,  # Less penalty for taking early
            ml_multiplier=5.0,  # Trust ML more
            fallback_risk_weight=0.05  # Care less about risk
        )
        
        # Conservative profile (prioritize safety and needs)
        self.profiles['conservative'] = ScoringConfig(
            profile_name='conservative',
            description='Conservative strategy prioritizing team needs',
            availability_penalty_85_100=-200.0,  # Heavy penalty for reaching
            position_need_bonus=120.0,  # Prioritize filling needs
            injury_risk_penalty=-50.0  # Avoid risky players
        )
        
        # Pitcher-heavy profile
        self.profiles['pitcher_heavy'] = ScoringConfig(
            profile_name='pitcher_heavy',
            description='Prioritize pitchers and IP accumulation',
            ip_accumulation_base_0_20=300.0,
            ip_contribution_per_ip=0.5,
            pitcher_scarcity_high=80.0,
            behind_pace_bonus=60.0
        )
        
        # Hitter-heavy profile
        self.profiles['hitter_heavy'] = ScoringConfig(
            profile_name='hitter_heavy',
            description='Prioritize hitters and offensive categories',
            hitter_lineup_bonus_0_2=350.0,
            category_weight_hr=3.5,
            category_weight_sb=5.0,
            pitcher_scarcity_high=25.0
        )
    
    def load_profile(self, profile_name: str) -> ScoringConfig:
        """
        Load a configuration profile.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            The loaded ScoringConfig
            
        Raises:
            ValueError: If profile not found
        """
        if profile_name in self.profiles:
            self.current_config = self.profiles[profile_name]
            return self.current_config
        
        # Try loading from file
        filepath = self.config_dir / f"{profile_name}.json"
        if filepath.exists():
            config = ScoringConfig.load_from_file(str(filepath))
            self.profiles[profile_name] = config
            self.current_config = config
            return config
        
        raise ValueError(f"Profile '{profile_name}' not found")
    
    def save_profile(self, config: ScoringConfig, profile_name: str = None):
        """
        Save a configuration profile.
        
        Args:
            config: The ScoringConfig to save
            profile_name: Optional name to save as (overrides config.profile_name)
        """
        if profile_name:
            config.profile_name = profile_name
        
        filepath = self.config_dir / f"{config.profile_name}.json"
        config.save_to_file(str(filepath))
        self.profiles[config.profile_name] = config
    
    def list_profiles(self) -> List[Dict[str, str]]:
        """
        List all available profiles.
        
        Returns:
            List of dicts with profile metadata (name, description, version)
        """
        profiles = []
        for name, config in self.profiles.items():
            profiles.append({
                'name': name,
                'description': config.description,
                'version': config.version
            })
        return profiles
    
    def get_current_config(self) -> ScoringConfig:
        """
        Get the currently active configuration.
        
        Returns:
            The current ScoringConfig
        """
        return self.current_config
    
    def reset_to_default(self):
        """Reset to default configuration by creating a fresh default profile."""
        # Create a fresh default profile instead of reusing the cached one
        # This ensures any modifications to the current config don't persist
        self.profiles['default'] = ScoringConfig(
            profile_name='default',
            description='Balanced scoring for most situations'
        )
        self.current_config = self.profiles['default']
