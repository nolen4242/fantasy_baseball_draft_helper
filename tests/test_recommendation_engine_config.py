"""
Integration tests for RecommendationEngine config integration.
"""

import pytest
import tempfile
from unittest.mock import Mock, MagicMock
from src.services.recommendation_engine import RecommendationEngine
from src.services.scoring_config import ScoringConfig
from src.services.draft_service import DraftService
from src.models.player import Player
from src.models.draft import DraftState


class TestRecommendationEngineConfig:
    """Test suite for RecommendationEngine configuration integration."""
    
    @pytest.fixture
    def mock_draft_service(self):
        """Create a mock draft service."""
        service = Mock(spec=DraftService)
        return service
    
    @pytest.fixture
    def recommendation_engine(self, mock_draft_service):
        """Create a recommendation engine instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = RecommendationEngine(mock_draft_service)
            # Override config_dir to use temp directory
            from pathlib import Path
            engine.config_manager.config_dir = Path(tmpdir)
            return engine
    
    def test_initialization_loads_config(self, recommendation_engine):
        """Test that initialization loads configuration."""
        assert hasattr(recommendation_engine, 'config_manager')
        assert hasattr(recommendation_engine, 'config')
        assert isinstance(recommendation_engine.config, ScoringConfig)
    
    def test_default_config_on_initialization(self, recommendation_engine):
        """Test that default config is loaded on initialization."""
        assert recommendation_engine.config.profile_name == 'default'
        assert recommendation_engine.config.standings_multiplier == 30.0
    
    def test_get_config(self, recommendation_engine):
        """Test getting current configuration."""
        config = recommendation_engine.get_config()
        
        assert isinstance(config, ScoringConfig)
        assert config == recommendation_engine.config
    
    def test_set_config_profile(self, recommendation_engine):
        """Test switching configuration profiles."""
        # Initially on default
        assert recommendation_engine.config.profile_name == 'default'
        
        # Switch to aggressive
        recommendation_engine.set_config_profile('aggressive')
        
        assert recommendation_engine.config.profile_name == 'aggressive'
        assert recommendation_engine.config.ml_multiplier == 5.0
    
    def test_set_config_profile_clears_cache(self, recommendation_engine):
        """Test that switching profiles clears the cache."""
        # Add something to cache
        recommendation_engine._cache['test_key'] = 'test_value'
        assert len(recommendation_engine._cache) > 0
        
        # Switch profile
        recommendation_engine.set_config_profile('conservative')
        
        # Cache should be cleared
        assert len(recommendation_engine._cache) == 0
    
    def test_set_config_profile_invalid(self, recommendation_engine):
        """Test that setting invalid profile raises error."""
        with pytest.raises(ValueError, match="Profile 'nonexistent' not found"):
            recommendation_engine.set_config_profile('nonexistent')
    
    def test_update_config(self, recommendation_engine):
        """Test updating specific config values."""
        original_multiplier = recommendation_engine.config.standings_multiplier
        
        recommendation_engine.update_config(standings_multiplier=40.0)
        
        assert recommendation_engine.config.standings_multiplier == 40.0
        assert recommendation_engine.config.standings_multiplier != original_multiplier
    
    def test_update_config_multiple_values(self, recommendation_engine):
        """Test updating multiple config values at once."""
        recommendation_engine.update_config(
            standings_multiplier=35.0,
            ml_multiplier=4.0,
            position_need_bonus=100.0
        )
        
        assert recommendation_engine.config.standings_multiplier == 35.0
        assert recommendation_engine.config.ml_multiplier == 4.0
        assert recommendation_engine.config.position_need_bonus == 100.0
    
    def test_update_config_clears_cache(self, recommendation_engine):
        """Test that updating config clears the cache."""
        # Add something to cache
        recommendation_engine._cache['test_key'] = 'test_value'
        assert len(recommendation_engine._cache) > 0
        
        # Update config
        recommendation_engine.update_config(standings_multiplier=35.0)
        
        # Cache should be cleared
        assert len(recommendation_engine._cache) == 0
    
    def test_update_config_ignores_invalid_attributes(self, recommendation_engine):
        """Test that updating invalid attributes is ignored."""
        # This should not raise an error, just be ignored
        recommendation_engine.update_config(
            standings_multiplier=35.0,
            invalid_attribute=999.0
        )
        
        assert recommendation_engine.config.standings_multiplier == 35.0
        assert not hasattr(recommendation_engine.config, 'invalid_attribute')
    
    def test_config_persists_across_profile_switches(self, recommendation_engine):
        """Test that config changes persist when switching back."""
        # Load aggressive profile
        recommendation_engine.set_config_profile('aggressive')
        original_ml = recommendation_engine.config.ml_multiplier
        
        # Switch to conservative
        recommendation_engine.set_config_profile('conservative')
        
        # Switch back to aggressive
        recommendation_engine.set_config_profile('aggressive')
        
        # Should have original aggressive values
        assert recommendation_engine.config.ml_multiplier == original_ml
    
    def test_all_default_profiles_accessible(self, recommendation_engine):
        """Test that all default profiles can be loaded."""
        profiles = ['default', 'aggressive', 'conservative', 'pitcher_heavy', 'hitter_heavy']
        
        for profile_name in profiles:
            recommendation_engine.set_config_profile(profile_name)
            assert recommendation_engine.config.profile_name == profile_name
    
    def test_config_manager_shared_state(self, recommendation_engine):
        """Test that config manager maintains state correctly."""
        # Get initial profile list
        profiles_before = recommendation_engine.config_manager.list_profiles()
        
        # Switch profiles
        recommendation_engine.set_config_profile('aggressive')
        
        # Profile list should still be the same
        profiles_after = recommendation_engine.config_manager.list_profiles()
        assert len(profiles_before) == len(profiles_after)
    
    def test_config_validation_accessible(self, recommendation_engine):
        """Test that config validation can be accessed."""
        errors = recommendation_engine.config.validate()
        
        # Default config should have no errors
        assert isinstance(errors, list)
        assert len(errors) == 0
    
    def test_config_changes_affect_calculations(self, recommendation_engine):
        """Test that config changes would affect calculations (structure test)."""
        # This is a structural test - we're verifying the config is accessible
        # Actual calculation tests would require full mock setup
        
        original_multiplier = recommendation_engine.config.standings_multiplier
        recommendation_engine.update_config(standings_multiplier=100.0)
        
        # Verify the change is reflected
        assert recommendation_engine.config.standings_multiplier == 100.0
        assert recommendation_engine.config.standings_multiplier != original_multiplier
        
        # Verify it's the same object being used
        assert recommendation_engine.get_config().standings_multiplier == 100.0
