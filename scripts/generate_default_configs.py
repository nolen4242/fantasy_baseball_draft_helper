"""
Script to generate default configuration profiles.
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.scoring_config import ScoringConfig


def generate_configs():
    """Generate all default configuration profiles."""
    config_dir = Path(__file__).parent.parent / "config" / "scoring"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Default profile
    default = ScoringConfig(
        profile_name='default',
        description='Balanced scoring for most situations'
    )
    default.save_to_file(str(config_dir / "default.json"))
    print(f"Created: {config_dir / 'default.json'}")
    
    # Aggressive profile
    aggressive = ScoringConfig(
        profile_name='aggressive',
        description='Aggressive value-seeking strategy',
        availability_penalty_85_100=-50.0,  # Less penalty for taking early
        ml_multiplier=5.0,  # Trust ML more
        fallback_risk_weight=0.05  # Care less about risk
    )
    aggressive.save_to_file(str(config_dir / "aggressive.json"))
    print(f"Created: {config_dir / 'aggressive.json'}")
    
    # Conservative profile
    conservative = ScoringConfig(
        profile_name='conservative',
        description='Conservative strategy prioritizing team needs',
        availability_penalty_85_100=-200.0,  # Heavy penalty for reaching
        position_need_bonus=120.0,  # Prioritize filling needs
        injury_risk_penalty=-50.0  # Avoid risky players
    )
    conservative.save_to_file(str(config_dir / "conservative.json"))
    print(f"Created: {config_dir / 'conservative.json'}")
    
    # Pitcher-heavy profile
    pitcher_heavy = ScoringConfig(
        profile_name='pitcher_heavy',
        description='Prioritize pitchers and IP accumulation',
        ip_accumulation_base_0_20=300.0,
        ip_contribution_per_ip=0.5,
        pitcher_scarcity_high=80.0,
        behind_pace_bonus=60.0
    )
    pitcher_heavy.save_to_file(str(config_dir / "pitcher_heavy.json"))
    print(f"Created: {config_dir / 'pitcher_heavy.json'}")
    
    # Hitter-heavy profile
    hitter_heavy = ScoringConfig(
        profile_name='hitter_heavy',
        description='Prioritize hitters and offensive categories',
        hitter_lineup_bonus_0_2=350.0,
        category_weight_hr=3.5,
        category_weight_sb=5.0,
        pitcher_scarcity_high=25.0
    )
    hitter_heavy.save_to_file(str(config_dir / "hitter_heavy.json"))
    print(f"Created: {config_dir / 'hitter_heavy.json'}")
    
    print("\nAll default configuration profiles created successfully!")


if __name__ == "__main__":
    generate_configs()
