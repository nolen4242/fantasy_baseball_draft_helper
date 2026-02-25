"""
Unit tests for ConfigManager.
"""

import pytest
import tempfile
from pathlib import Path
from src.services.config_manager import ConfigManager
from src.services.scoring_config import ScoringConfig


class TestConfigManager:
    """Test suite for ConfigManager class."""
    
    def test_initialization(self):
        """Test that ConfigManager initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            assert manager.config_dir == Path(tmpdir)
            assert manager.config_dir.exists()
            assert isinstance(manager.current_config, ScoringConfig)
            assert len(manager.profiles) > 0
    
    def test_initialization_default_path(self):
        """Test that ConfigManager uses default path when config_dir is None."""
        manager = ConfigManager(config_dir=None)
        
        # Should create default path
        assert manager.config_dir is not None
        assert manager.config_dir.exists()
        assert "config" in str(manager.config_dir)
        assert "scoring" in str(manager.config_dir)
    
    def test_initialization_creates_directory(self):
        """Test that initialization creates config directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config"
            manager = ConfigManager(config_dir=str(config_path))
            
            assert config_path.exists()
    
    def test_default_profiles_loaded(self):
        """Test that default profiles are loaded on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            assert 'default' in manager.profiles
            assert 'aggressive' in manager.profiles
            assert 'conservative' in manager.profiles
            assert 'pitcher_heavy' in manager.profiles
            assert 'hitter_heavy' in manager.profiles
    
    def test_default_profile_values(self):
        """Test that default profile has correct values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            default = manager.profiles['default']
            assert default.profile_name == 'default'
            assert default.description == 'Balanced scoring for most situations'
            assert default.standings_multiplier == 30.0
    
    def test_aggressive_profile_values(self):
        """Test that aggressive profile has modified values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            aggressive = manager.profiles['aggressive']
            assert aggressive.profile_name == 'aggressive'
            assert aggressive.ml_multiplier == 5.0
            assert aggressive.availability_penalty_85_100 == -50.0
    
    def test_conservative_profile_values(self):
        """Test that conservative profile has modified values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            conservative = manager.profiles['conservative']
            assert conservative.profile_name == 'conservative'
            assert conservative.position_need_bonus == 120.0
            assert conservative.injury_risk_penalty == -50.0
    
    def test_pitcher_heavy_profile_values(self):
        """Test that pitcher_heavy profile has modified values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            pitcher_heavy = manager.profiles['pitcher_heavy']
            assert pitcher_heavy.profile_name == 'pitcher_heavy'
            assert pitcher_heavy.ip_accumulation_base_0_20 == 300.0
            assert pitcher_heavy.pitcher_scarcity_high == 80.0
    
    def test_hitter_heavy_profile_values(self):
        """Test that hitter_heavy profile has modified values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            hitter_heavy = manager.profiles['hitter_heavy']
            assert hitter_heavy.profile_name == 'hitter_heavy'
            assert hitter_heavy.hitter_lineup_bonus_0_2 == 350.0
            assert hitter_heavy.category_weight_sb == 5.0
    
    def test_load_profile_from_memory(self):
        """Test loading a profile that's already in memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            config = manager.load_profile('aggressive')
            
            assert config.profile_name == 'aggressive'
            assert manager.current_config.profile_name == 'aggressive'
    
    def test_load_profile_from_file(self):
        """Test loading a profile from a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Create a custom profile and save it
            custom = ScoringConfig(
                profile_name='custom',
                description='Custom profile',
                standings_multiplier=40.0
            )
            custom.save_to_file(str(Path(tmpdir) / "custom.json"))
            
            # Clear profiles to force file load
            manager.profiles = {'default': manager.profiles['default']}
            
            # Load from file
            loaded = manager.load_profile('custom')
            
            assert loaded.profile_name == 'custom'
            assert loaded.standings_multiplier == 40.0
            assert manager.current_config.profile_name == 'custom'
    
    def test_load_profile_not_found(self):
        """Test that loading non-existent profile raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            with pytest.raises(ValueError, match="Profile 'nonexistent' not found"):
                manager.load_profile('nonexistent')
    
    def test_save_profile(self):
        """Test saving a profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            custom = ScoringConfig(
                profile_name='test_save',
                description='Test save',
                standings_multiplier=35.0
            )
            
            manager.save_profile(custom)
            
            # Check file was created
            filepath = Path(tmpdir) / "test_save.json"
            assert filepath.exists()
            
            # Check profile is in memory
            assert 'test_save' in manager.profiles
            assert manager.profiles['test_save'].standings_multiplier == 35.0
    
    def test_save_profile_with_custom_name(self):
        """Test saving a profile with a different name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            config = ScoringConfig(
                profile_name='original',
                standings_multiplier=35.0
            )
            
            manager.save_profile(config, profile_name='renamed')
            
            # Check file was created with new name
            filepath = Path(tmpdir) / "renamed.json"
            assert filepath.exists()
            
            # Check profile name was updated
            assert config.profile_name == 'renamed'
            assert 'renamed' in manager.profiles
    
    def test_list_profiles(self):
        """Test listing all profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            profiles = manager.list_profiles()
            
            assert isinstance(profiles, list)
            assert len(profiles) >= 5  # At least the 5 default profiles
            
            # Check structure
            for profile in profiles:
                assert 'name' in profile
                assert 'description' in profile
                assert 'version' in profile
    
    def test_list_profiles_contains_defaults(self):
        """Test that list_profiles includes all default profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            profiles = manager.list_profiles()
            profile_names = [p['name'] for p in profiles]
            
            assert 'default' in profile_names
            assert 'aggressive' in profile_names
            assert 'conservative' in profile_names
            assert 'pitcher_heavy' in profile_names
            assert 'hitter_heavy' in profile_names
    
    def test_get_current_config(self):
        """Test getting the current configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            current = manager.get_current_config()
            
            assert isinstance(current, ScoringConfig)
            assert current == manager.current_config
    
    def test_get_current_config_after_load(self):
        """Test that current config updates after loading a profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            manager.load_profile('aggressive')
            current = manager.get_current_config()
            
            assert current.profile_name == 'aggressive'
    
    def test_reset_to_default(self):
        """Test resetting to default configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Load a different profile
            manager.load_profile('aggressive')
            assert manager.current_config.profile_name == 'aggressive'
            
            # Reset to default
            manager.reset_to_default()
            
            assert manager.current_config.profile_name == 'default'
    
    def test_profile_independence(self):
        """Test that modifying one profile doesn't affect others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Get two profiles
            default = manager.profiles['default']
            aggressive = manager.profiles['aggressive']
            
            # They should have different values
            assert default.ml_multiplier != aggressive.ml_multiplier
            
            # Modifying one shouldn't affect the other
            original_default_ml = default.ml_multiplier
            aggressive.ml_multiplier = 10.0
            
            assert default.ml_multiplier == original_default_ml
    
    def test_save_and_reload_profile(self):
        """Test that saved profiles can be reloaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager(config_dir=tmpdir)
            
            # Create and save a custom profile
            custom = ScoringConfig(
                profile_name='roundtrip',
                description='Test roundtrip',
                standings_multiplier=42.0,
                ml_multiplier=7.0
            )
            manager.save_profile(custom)
            
            # Create a new manager (simulating restart)
            manager2 = ConfigManager(config_dir=tmpdir)
            
            # Load the saved profile
            loaded = manager2.load_profile('roundtrip')
            
            assert loaded.profile_name == 'roundtrip'
            assert loaded.description == 'Test roundtrip'
            assert loaded.standings_multiplier == 42.0
            assert loaded.ml_multiplier == 7.0
