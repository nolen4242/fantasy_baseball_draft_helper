"""
Backward compatibility tests for recommendation engine with config system.

These tests verify that existing drafts continue to work correctly with the
new configuration infrastructure, and that default behavior is unchanged.
"""

import pytest
import json
from pathlib import Path
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.models.draft import DraftState
from src.models.player import Player


class TestBackwardCompatibility:
    """Test suite for backward compatibility with existing drafts."""
    
    @pytest.fixture
    def player_loader(self):
        """Create a master player dict loader instance."""
        return MasterPlayerDictLoader()
    
    @pytest.fixture
    def all_players(self, player_loader):
        """Load all players from master player dict."""
        return player_loader.load_all_players()
    
    @pytest.fixture
    def draft_service(self):
        """Create a draft service instance."""
        return DraftService()
    
    @pytest.fixture
    def recommendation_engine(self, draft_service, all_players):
        """Create a recommendation engine instance."""
        return RecommendationEngine(draft_service, all_players)
    
    @pytest.fixture
    def test_draft_state(self, draft_service):
        """Load a test draft state."""
        draft_file = Path("data/teams/test_draft.json")
        if not draft_file.exists():
            pytest.skip("Test draft file not found")
        
        with open(draft_file, 'r') as f:
            draft_data = json.load(f)
        
        return DraftState(
            draft_id=draft_data['draft_id'],
            league_name=draft_data['league_name'],
            total_teams=draft_data['total_teams'],
            roster_size=draft_data['roster_size'],
            my_team_name=draft_data['my_team_name'],
            current_pick=draft_data['current_pick'],
            current_round=draft_data['current_round'],
            picks=draft_data.get('picks', []),
            team_rosters=draft_data['team_rosters'],
            is_complete=draft_data.get('is_complete', False)
        )
    
    def test_existing_draft_loads_successfully(self, test_draft_state):
        """Test that existing draft files can be loaded."""
        assert test_draft_state is not None
        assert test_draft_state.draft_id == "test_draft"
        assert test_draft_state.my_team_name == "Runtime Terror"
        assert test_draft_state.total_teams == 13
    
    def test_recommendations_work_with_existing_draft(
        self, recommendation_engine, test_draft_state, all_players
    ):
        """Test that recommendations work with existing draft state."""
        # Get available players (all players since draft hasn't started)
        available_players = [p for p in all_players if p.player_id not in 
                           [pid for roster in test_draft_state.team_rosters.values() 
                            for pid in roster]]
        
        # Get my team (empty at start)
        my_team = []
        
        # Get recommendations
        recommendations = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False  # Skip ML for faster test
        )
        
        # Verify recommendations are returned
        assert recommendations is not None
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Verify recommendation structure
        for rec in recommendations:
            assert 'player' in rec
            assert 'score' in rec
            assert 'reasoning' in rec
            assert isinstance(rec['player'], Player)
            assert isinstance(rec['score'], (int, float))
            assert isinstance(rec['reasoning'], str)
    
    def test_default_config_values_match_original(self, recommendation_engine):
        """Test that default config values match original hardcoded values."""
        config = recommendation_engine.get_config()
        
        # Verify primary factors
        assert config.standings_multiplier == 30.0
        
        # Verify roster balance - IP accumulation
        assert config.ip_accumulation_base_0_20 == 200.0
        assert config.ip_accumulation_base_20_50 == 150.0
        assert config.ip_accumulation_base_50_80 == 100.0
        assert config.ip_accumulation_base_80_100 == 50.0
        assert config.ip_contribution_per_ip == 0.3
        
        # Verify roster balance - Hitter lineup
        assert config.hitter_lineup_bonus_0_2 == 260.0
        assert config.hitter_lineup_bonus_3_5 == 150.0
        assert config.hitter_lineup_bonus_6_8 == 75.0
        
        # Verify ML model
        assert config.ml_multiplier == 3.0
        
        # Verify future availability
        assert config.availability_bonus_0_10 == 120.0
        assert config.availability_bonus_10_30 == 80.0
        assert config.availability_bonus_30_50 == 30.0
        assert config.availability_penalty_50_70 == -30.0
        assert config.availability_penalty_70_85 == -80.0
        assert config.availability_penalty_85_100 == -150.0
    
    def test_config_does_not_break_existing_methods(self, recommendation_engine):
        """Test that config system doesn't break existing method signatures."""
        # Verify all expected methods exist
        assert hasattr(recommendation_engine, 'get_recommendations')
        assert hasattr(recommendation_engine, 'get_recommendations_for_team')
        assert hasattr(recommendation_engine, '_calculate_player_value')
        assert hasattr(recommendation_engine, '_calculate_standings_improvement')
        
        # Verify new config methods exist
        assert hasattr(recommendation_engine, 'get_config')
        assert hasattr(recommendation_engine, 'set_config_profile')
        assert hasattr(recommendation_engine, 'update_config')
    
    def test_recommendations_consistent_with_default_config(
        self, recommendation_engine, test_draft_state, all_players
    ):
        """Test that recommendations with default config are consistent."""
        # Get available players
        available_players = [p for p in all_players if p.player_id not in 
                           [pid for roster in test_draft_state.team_rosters.values() 
                            for pid in roster]]
        my_team = []
        
        # Get recommendations twice with default config
        recs1 = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        recs2 = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify recommendations are identical
        assert len(recs1) == len(recs2)
        for i in range(len(recs1)):
            assert recs1[i]['player'].player_id == recs2[i]['player'].player_id
            assert abs(recs1[i]['score'] - recs2[i]['score']) < 0.01
    
    def test_profile_switching_does_not_break_recommendations(
        self, recommendation_engine, test_draft_state, all_players
    ):
        """Test that switching profiles doesn't break recommendations."""
        available_players = [p for p in all_players if p.player_id not in 
                           [pid for roster in test_draft_state.team_rosters.values() 
                            for pid in roster]]
        my_team = []
        
        # Get recommendations with default profile
        recs_default = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Switch to aggressive profile
        recommendation_engine.set_config_profile('aggressive')
        
        # Get recommendations with aggressive profile
        recs_aggressive = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Switch back to default
        recommendation_engine.set_config_profile('default')
        
        # Get recommendations again
        recs_back_to_default = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify all recommendation sets are valid
        assert len(recs_default) > 0
        assert len(recs_aggressive) > 0
        assert len(recs_back_to_default) > 0
        
        # Verify switching back to default gives same results
        assert len(recs_default) == len(recs_back_to_default)
        for i in range(len(recs_default)):
            assert recs_default[i]['player'].player_id == recs_back_to_default[i]['player'].player_id
    
    def test_config_updates_do_not_break_recommendations(
        self, recommendation_engine, test_draft_state, all_players
    ):
        """Test that updating config values doesn't break recommendations."""
        available_players = [p for p in all_players if p.player_id not in 
                           [pid for roster in test_draft_state.team_rosters.values() 
                            for pid in roster]]
        my_team = []
        
        # Get recommendations with default config
        recs_before = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Update config values
        recommendation_engine.update_config(
            standings_multiplier=35.0,
            ml_multiplier=5.0
        )
        
        # Get recommendations with updated config
        recs_after = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify recommendations still work
        assert len(recs_before) > 0
        assert len(recs_after) > 0
        
        # Verify structure is intact
        for rec in recs_after:
            assert 'player' in rec
            assert 'score' in rec
            assert 'reasoning' in rec
    
    def test_existing_draft_with_picks_works(
        self, recommendation_engine, draft_service, all_players
    ):
        """Test that drafts with existing picks continue to work."""
        # Create a draft state with some picks
        draft_state = DraftState(
            draft_id="test_with_picks",
            league_name="Bob Uecker League",
            total_teams=13,
            roster_size=21,
            my_team_name="Runtime Terror",
            current_pick=3,
            current_round=1,
            picks=[],
            team_rosters={
                "Runtime Terror": [],
                "Dawg": [],
                "Long Balls": []
            },
            is_complete=False
        )
        
        # Simulate some picks
        if len(all_players) >= 2:
            draft_state.team_rosters["Dawg"] = [all_players[0].player_id]
            draft_state.team_rosters["Long Balls"] = [all_players[1].player_id]
        
        # Get available players
        drafted_ids = [pid for roster in draft_state.team_rosters.values() for pid in roster]
        available_players = [p for p in all_players if p.player_id not in drafted_ids]
        my_team = []
        
        # Get recommendations
        recommendations = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify recommendations work
        assert len(recommendations) > 0
        
        # Verify drafted players are not recommended
        recommended_ids = [rec['player'].player_id for rec in recommendations]
        for drafted_id in drafted_ids:
            assert drafted_id not in recommended_ids
    
    def test_cache_invalidation_works_correctly(
        self, recommendation_engine, test_draft_state, all_players
    ):
        """Test that cache is properly invalidated when config changes."""
        available_players = [p for p in all_players if p.player_id not in 
                           [pid for roster in test_draft_state.team_rosters.values() 
                            for pid in roster]]
        my_team = []
        
        # Get recommendations (populates cache)
        recs1 = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify cache has entries
        assert len(recommendation_engine._cache) > 0
        
        # Update config (should clear cache)
        recommendation_engine.update_config(standings_multiplier=35.0)
        
        # Verify cache was cleared
        assert len(recommendation_engine._cache) == 0
        
        # Get recommendations again (should work)
        recs2 = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=test_draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify recommendations still work
        assert len(recs2) > 0
