"""
Unit tests for ScoringConfig.
"""

import pytest
import json
import tempfile
from pathlib import Path
from src.services.scoring_config import ScoringConfig


class TestScoringConfig:
    """Test suite for ScoringConfig class."""
    
    def test_default_initialization(self):
        """Test that ScoringConfig initializes with default values."""
        config = ScoringConfig()
        
        assert config.standings_multiplier == 30.0
        assert config.ml_multiplier == 3.0
        assert config.ip_accumulation_base_0_20 == 200.0
        assert config.profile_name == "default"
        assert config.version == "1.0"
    
    def test_custom_initialization(self):
        """Test that ScoringConfig can be initialized with custom values."""
        config = ScoringConfig(
            standings_multiplier=40.0,
            ml_multiplier=5.0,
            profile_name="custom"
        )
        
        assert config.standings_multiplier == 40.0
        assert config.ml_multiplier == 5.0
        assert config.profile_name == "custom"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ScoringConfig(
            standings_multiplier=35.0,
            profile_name="test"
        )
        
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['standings_multiplier'] == 35.0
        assert config_dict['profile_name'] == "test"
        assert 'ml_multiplier' in config_dict
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'standings_multiplier': 25.0,
            'ml_multiplier': 4.0,
            'profile_name': 'from_dict',
            'description': 'Test config',
            'version': '1.0'
        }
        
        config = ScoringConfig.from_dict(data)
        
        assert config.standings_multiplier == 25.0
        assert config.ml_multiplier == 4.0
        assert config.profile_name == 'from_dict'
    
    def test_save_and_load_from_file(self):
        """Test saving to and loading from JSON file."""
        config = ScoringConfig(
            standings_multiplier=45.0,
            ml_multiplier=6.0,
            profile_name="test_save"
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_config.json"
            
            # Save
            config.save_to_file(str(filepath))
            assert filepath.exists()
            
            # Load
            loaded_config = ScoringConfig.load_from_file(str(filepath))
            assert loaded_config.standings_multiplier == 45.0
            assert loaded_config.ml_multiplier == 6.0
            assert loaded_config.profile_name == "test_save"
    
    def test_save_creates_directory(self):
        """Test that save_to_file creates parent directories if needed."""
        config = ScoringConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "config.json"
            
            config.save_to_file(str(filepath))
            assert filepath.exists()
    
    def test_validate_positive_multipliers(self):
        """Test validation catches negative multipliers."""
        config = ScoringConfig(standings_multiplier=-10.0)
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("standings_multiplier must be positive" in e for e in errors)
    
    def test_validate_ml_multiplier(self):
        """Test validation catches negative ML multiplier."""
        config = ScoringConfig(ml_multiplier=-5.0)
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("ml_multiplier must be positive" in e for e in errors)
    
    def test_validate_ip_accumulation_range(self):
        """Test validation catches out-of-range IP accumulation values."""
        config = ScoringConfig(ip_accumulation_base_0_20=600.0)
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("ip_accumulation_base_0_20 should be 0-500" in e for e in errors)
    
    def test_validate_fallback_weights_sum(self):
        """Test validation checks fallback weights sum to ~1.0."""
        config = ScoringConfig(
            fallback_adp_weight=0.1,
            fallback_team_needs_weight=0.1,
            fallback_position_scarcity_weight=0.1,
            fallback_category_targeting_weight=0.1,
            fallback_relative_advantage_weight=0.1,
            fallback_risk_weight=0.1
        )
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("Fallback weights sum to" in e for e in errors)
    
    def test_validate_autodraft_weights_sum(self):
        """Test validation checks auto-draft weights sum to ~1.0."""
        config = ScoringConfig(
            autodraft_adp_weight=0.2,
            autodraft_team_needs_weight=0.2,
            autodraft_position_scarcity_weight=0.2
        )
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("Auto-draft weights sum to" in e for e in errors)
    
    def test_validate_valid_config(self):
        """Test that default config passes validation."""
        config = ScoringConfig()
        errors = config.validate()
        
        assert len(errors) == 0
    
    def test_all_weights_present(self):
        """Test that all expected weight attributes are present."""
        config = ScoringConfig()
        
        # Primary factors
        assert hasattr(config, 'standings_multiplier')
        assert hasattr(config, 'ml_multiplier')
        
        # Roster balance
        assert hasattr(config, 'ip_accumulation_base_0_20')
        assert hasattr(config, 'ip_contribution_per_ip')
        assert hasattr(config, 'hitter_lineup_bonus_0_2')
        
        # Availability
        assert hasattr(config, 'availability_bonus_0_10')
        assert hasattr(config, 'availability_penalty_85_100')
        
        # Team needs
        assert hasattr(config, 'position_need_bonus')
        assert hasattr(config, 'redundant_position_penalty')
        
        # Position scarcity
        assert hasattr(config, 'elite_position_scarce')
        assert hasattr(config, 'pitcher_scarcity_high')
        
        # Category targeting
        assert hasattr(config, 'category_weight_hr')
        assert hasattr(config, 'category_weight_sb')
        
        # Relative advantage
        assert hasattr(config, 'relative_advantage_multiplier')
        
        # Risk assessment
        assert hasattr(config, 'injury_risk_penalty')
        
        # Fallback weights
        assert hasattr(config, 'fallback_adp_weight')
        
        # Auto-draft weights
        assert hasattr(config, 'autodraft_adp_weight')
    
    def test_json_serialization_roundtrip(self):
        """Test that config can be serialized and deserialized without loss."""
        original = ScoringConfig(
            standings_multiplier=33.0,
            ml_multiplier=4.5,
            profile_name="roundtrip_test"
        )
        
        # Convert to dict, then to JSON string, then back
        config_dict = original.to_dict()
        json_str = json.dumps(config_dict)
        loaded_dict = json.loads(json_str)
        restored = ScoringConfig.from_dict(loaded_dict)
        
        assert restored.standings_multiplier == original.standings_multiplier
        assert restored.ml_multiplier == original.ml_multiplier
        assert restored.profile_name == original.profile_name
