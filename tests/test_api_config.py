"""
API tests for recommendation engine configuration endpoints.
"""

import pytest
import json
from src.api.app import app
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def reset_engine():
    """Reset recommendation engine to default config after each test."""
    yield
    # Reset to default after test
    from src.api.app import recommendation_engine
    try:
        recommendation_engine.config_manager.reset_to_default()
        recommendation_engine.config = recommendation_engine.config_manager.get_current_config()
        recommendation_engine._cache.clear()
    except:
        pass


class TestConfigEndpoints:
    """Test suite for configuration API endpoints."""
    
    def test_get_config_returns_current_config(self, client, reset_engine):
        """Test GET /api/recommendations/config returns current config."""
        response = client.get('/api/recommendations/config')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'config' in data
        assert 'profile_name' in data['config']
        assert 'standings_multiplier' in data['config']
        assert data['config']['profile_name'] == 'default'
    
    def test_get_config_includes_all_weights(self, client, reset_engine):
        """Test that config includes all expected weight fields."""
        response = client.get('/api/recommendations/config')
        data = json.loads(response.data)
        
        config = data['config']
        
        # Check for key weight fields
        expected_fields = [
            'standings_multiplier',
            'ml_multiplier',
            'ip_accumulation_base_0_20',
            'hitter_lineup_bonus_0_2',
            'availability_bonus_0_10',
            'position_need_bonus',
            'elite_position_scarce',
            'category_weight_hr',
            'relative_advantage_multiplier',
            'injury_risk_penalty'
        ]
        
        for field in expected_fields:
            assert field in config, f"Missing field: {field}"
    
    def test_list_profiles_returns_all_profiles(self, client, reset_engine):
        """Test GET /api/recommendations/config/profiles returns all profiles."""
        response = client.get('/api/recommendations/config/profiles')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'profiles' in data
        assert isinstance(data['profiles'], list)
        assert len(data['profiles']) >= 5  # At least 5 default profiles
        
        # Check profile structure
        profile_names = [p['name'] for p in data['profiles']]
        assert 'default' in profile_names
        assert 'aggressive' in profile_names
        assert 'conservative' in profile_names
        assert 'pitcher_heavy' in profile_names
        assert 'hitter_heavy' in profile_names
        
        # Check each profile has required fields
        for profile in data['profiles']:
            assert 'name' in profile
            assert 'description' in profile
            assert 'version' in profile
    
    def test_set_profile_switches_config(self, client, reset_engine):
        """Test POST /api/recommendations/config/profile switches profiles."""
        # Switch to aggressive profile
        response = client.post(
            '/api/recommendations/config/profile',
            data=json.dumps({'profile_name': 'aggressive'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['profile'] == 'aggressive'
        assert 'message' in data
        
        # Verify the config was actually changed
        response = client.get('/api/recommendations/config')
        config_data = json.loads(response.data)
        
        assert config_data['config']['profile_name'] == 'aggressive'
        assert config_data['config']['ml_multiplier'] == 5.0  # Aggressive profile value
    
    def test_set_profile_invalid_returns_404(self, client, reset_engine):
        """Test POST with invalid profile name returns 404."""
        response = client.post(
            '/api/recommendations/config/profile',
            data=json.dumps({'profile_name': 'nonexistent'}),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'message' in data
        assert 'not found' in data['message'].lower()
    
    def test_set_profile_missing_name_returns_400(self, client, reset_engine):
        """Test POST without profile_name returns 400."""
        response = client.post(
            '/api/recommendations/config/profile',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'required' in data['message'].lower()
    
    def test_update_config_updates_values(self, client, reset_engine):
        """Test PATCH /api/recommendations/config updates values."""
        # Update specific values
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({
                'standings_multiplier': 40.0,
                'ml_multiplier': 4.5
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'updated' in data
        assert 'standings_multiplier' in data['updated']
        assert 'ml_multiplier' in data['updated']
        
        # Verify the values were actually updated
        response = client.get('/api/recommendations/config')
        config_data = json.loads(response.data)
        
        assert config_data['config']['standings_multiplier'] == 40.0
        assert config_data['config']['ml_multiplier'] == 4.5
    
    def test_update_config_ignores_invalid_fields(self, client, reset_engine):
        """Test PATCH ignores invalid field names."""
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({
                'standings_multiplier': 35.0,
                'invalid_field': 999.0
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        # Only valid field should be in updated list
        assert 'standings_multiplier' in data['updated']
        assert 'invalid_field' not in data['updated']
    
    def test_update_config_empty_returns_400(self, client, reset_engine):
        """Test PATCH with no values returns 400."""
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'no configuration values' in data['message'].lower()
    
    def test_update_config_all_invalid_returns_400(self, client, reset_engine):
        """Test PATCH with only invalid fields returns 400."""
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({
                'invalid_field1': 100.0,
                'invalid_field2': 200.0
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'no valid configuration fields' in data['message'].lower()
    
    def test_reset_config_returns_to_default(self, client, reset_engine):
        """Test POST /api/recommendations/config/reset returns to default."""
        # First, change to a different profile
        client.post(
            '/api/recommendations/config/profile',
            data=json.dumps({'profile_name': 'aggressive'}),
            content_type='application/json'
        )
        
        # Verify we're on aggressive
        response = client.get('/api/recommendations/config')
        data = json.loads(response.data)
        assert data['config']['profile_name'] == 'aggressive'
        
        # Reset to default
        response = client.post('/api/recommendations/config/reset')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'message' in data
        
        # Verify we're back on default
        response = client.get('/api/recommendations/config')
        config_data = json.loads(response.data)
        
        assert config_data['config']['profile_name'] == 'default'
        assert config_data['config']['standings_multiplier'] == 30.0  # Default value
    
    def test_config_changes_persist_across_requests(self, client, reset_engine):
        """Test that config changes persist across multiple requests."""
        # Update config
        client.patch(
            '/api/recommendations/config',
            data=json.dumps({'standings_multiplier': 50.0}),
            content_type='application/json'
        )
        
        # Make multiple GET requests
        for _ in range(3):
            response = client.get('/api/recommendations/config')
            data = json.loads(response.data)
            assert data['config']['standings_multiplier'] == 50.0
    
    def test_profile_switch_affects_all_weights(self, client, reset_engine):
        """Test that switching profiles changes multiple weights."""
        # Get default config
        response = client.get('/api/recommendations/config')
        default_config = json.loads(response.data)['config']
        
        # Switch to conservative
        client.post(
            '/api/recommendations/config/profile',
            data=json.dumps({'profile_name': 'conservative'}),
            content_type='application/json'
        )
        
        # Get conservative config
        response = client.get('/api/recommendations/config')
        conservative_config = json.loads(response.data)['config']
        
        # Verify multiple weights changed
        assert conservative_config['profile_name'] == 'conservative'
        assert conservative_config['position_need_bonus'] != default_config['position_need_bonus']
        assert conservative_config['injury_risk_penalty'] != default_config['injury_risk_penalty']
    
    def test_error_handling_returns_json(self, client, reset_engine):
        """Test that all errors return JSON responses."""
        # Test various error scenarios
        error_requests = [
            ('post', '/api/recommendations/config/profile', {'profile_name': 'invalid'}),
            ('patch', '/api/recommendations/config', {}),
            ('patch', '/api/recommendations/config', {'invalid': 123}),
        ]
        
        for method, url, data in error_requests:
            if method == 'post':
                response = client.post(url, data=json.dumps(data), content_type='application/json')
            else:
                response = client.patch(url, data=json.dumps(data), content_type='application/json')
            
            # All should return JSON
            assert response.content_type == 'application/json'
            data = json.loads(response.data)
            assert 'success' in data
            assert data['success'] is False
            assert 'message' in data


class TestConfigValidation:
    """Test suite for configuration validation in API."""
    
    def test_update_config_validates_values(self, client, reset_engine):
        """Test that PATCH validates configuration values."""
        # Try to set invalid fallback weights (should sum to ~1.0)
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({
                'fallback_adp_weight': 10.0,  # Way too high
                'fallback_team_needs_weight': 10.0,
                'fallback_position_scarcity_weight': 10.0
            }),
            content_type='application/json'
        )
        
        # Should return 400 with validation errors
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'validation' in data['message'].lower()
        assert 'errors' in data
        assert len(data['errors']) > 0
    
    def test_valid_config_passes_validation(self, client, reset_engine):
        """Test that valid config updates pass validation."""
        response = client.patch(
            '/api/recommendations/config',
            data=json.dumps({
                'standings_multiplier': 35.0,
                'ml_multiplier': 4.0
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


class TestConfigIntegration:
    """Integration tests for config API with other endpoints."""
    
    def test_config_affects_recommendations(self, client, reset_engine):
        """Test that config changes would affect recommendations (structure test)."""
        # This is a structural test - we verify the config is accessible
        # Full recommendation testing would require draft setup
        
        # Get initial config
        response = client.get('/api/recommendations/config')
        initial_config = json.loads(response.data)['config']
        
        # Update config
        client.patch(
            '/api/recommendations/config',
            data=json.dumps({'standings_multiplier': 100.0}),
            content_type='application/json'
        )
        
        # Verify config changed
        response = client.get('/api/recommendations/config')
        updated_config = json.loads(response.data)['config']
        
        assert updated_config['standings_multiplier'] == 100.0
        assert updated_config['standings_multiplier'] != initial_config['standings_multiplier']
