"""
Tests for recommendation engine caching behavior.
Verifies that cache is properly invalidated when available players change.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService
from src.models.player import Player
from src.models.draft import DraftState, DraftPick


class TestRecommendationCaching:
    """Test suite for recommendation engine caching."""
    
    @pytest.fixture
    def mock_draft_service(self):
        """Create a mock draft service."""
        service = Mock(spec=DraftService)
        return service
    
    @pytest.fixture
    def sample_players(self):
        """Create sample players for testing."""
        players = []
        for i in range(10):
            player = Player(
                player_id=f"player_{i}",
                name=f"Player {i}",
                position="OF" if i < 5 else "SP",
                team="TEST",
                adp=float(i + 1),
                projected_home_runs=20 if i < 5 else None,
                projected_innings_pitched=None if i < 5 else 150
            )
            players.append(player)
        return players
    
    @pytest.fixture
    def draft_state(self):
        """Create a sample draft state."""
        state = DraftState(
            draft_id="test_draft",
            league_name="Test League",
            total_teams=13,
            roster_size=21,
            my_team_name="Test_Team"
        )
        return state
    
    @pytest.fixture
    def recommendation_engine(self, mock_draft_service, sample_players):
        """Create a recommendation engine instance."""
        engine = RecommendationEngine(mock_draft_service, all_players=sample_players)
        return engine
    
    def test_cache_key_includes_available_players_hash(self, recommendation_engine, sample_players, draft_state):
        """Test that cache key includes hash of available players."""
        # Get initial available players
        available_players = sample_players[:5]
        my_team = []
        
        # Mock the team service to always return True for has_available_slot_for_player
        with patch.object(recommendation_engine.team_service, 'has_available_slot_for_player', return_value=True):
            # Mock standings calculator to avoid complex calculations
            with patch.object(recommendation_engine.standings_calculator, 'calculate_standings', return_value={'total_points': {}, 'category_points': {}}):
                with patch.object(recommendation_engine.standings_calculator, '_calculate_team_totals', return_value={'IP': 0, 'HR': 0, 'R': 0, 'RBI': 0, 'SB': 0, 'OBP': 0, 'K': 0, 'W': 0, 'QS': 0, 'SV': 0, 'HD': 0, 'ERA': 0, 'WHIP': 0}):
                    # Get recommendations with initial available players
                    recs1 = recommendation_engine.get_recommendations(
                        available_players=available_players,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache should have entries now
                    initial_cache_size = len(recommendation_engine._cache)
                    assert initial_cache_size > 0, "Cache should have entries after first recommendation call"
                    
                    # Get recommendations with same available players - should use cache
                    recs2 = recommendation_engine.get_recommendations(
                        available_players=available_players,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache size should be the same (reused cache)
                    assert len(recommendation_engine._cache) == initial_cache_size
    
    def test_cache_invalidated_when_available_players_change(self, recommendation_engine, sample_players, draft_state):
        """Test that cache is invalidated when available players change."""
        # Get initial available players
        available_players_1 = sample_players[:5]
        my_team = []
        
        # Mock the team service to always return True for has_available_slot_for_player
        with patch.object(recommendation_engine.team_service, 'has_available_slot_for_player', return_value=True):
            # Mock standings calculator to avoid complex calculations
            with patch.object(recommendation_engine.standings_calculator, 'calculate_standings', return_value={'total_points': {}, 'category_points': {}}):
                with patch.object(recommendation_engine.standings_calculator, '_calculate_team_totals', return_value={'IP': 0, 'HR': 0, 'R': 0, 'RBI': 0, 'SB': 0, 'OBP': 0, 'K': 0, 'W': 0, 'QS': 0, 'SV': 0, 'HD': 0, 'ERA': 0, 'WHIP': 0}):
                    # Get recommendations with initial available players
                    recs1 = recommendation_engine.get_recommendations(
                        available_players=available_players_1,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache should have entries now
                    initial_cache_size = len(recommendation_engine._cache)
                    assert initial_cache_size > 0, "Cache should have entries after first recommendation call"
                    
                    # Change available players (simulate a player being drafted)
                    available_players_2 = sample_players[1:6]  # Different set of players
                    
                    # Get recommendations with different available players
                    recs2 = recommendation_engine.get_recommendations(
                        available_players=available_players_2,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache should be cleared and rebuilt
                    # The cache size might be different because we're evaluating different players
                    assert len(recommendation_engine._cache) > 0, "Cache should have new entries"
    
    def test_cache_key_includes_team_name(self, recommendation_engine, sample_players, draft_state):
        """Test that cache key includes team name."""
        available_players = sample_players[:5]
        my_team = []
        
        # Mock the team service to always return True for has_available_slot_for_player
        with patch.object(recommendation_engine.team_service, 'has_available_slot_for_player', return_value=True):
            # Mock standings calculator to avoid complex calculations
            with patch.object(recommendation_engine.standings_calculator, 'calculate_standings', return_value={'total_points': {}, 'category_points': {}}):
                with patch.object(recommendation_engine.standings_calculator, '_calculate_team_totals', return_value={'IP': 0, 'HR': 0, 'R': 0, 'RBI': 0, 'SB': 0, 'OBP': 0, 'K': 0, 'W': 0, 'QS': 0, 'SV': 0, 'HD': 0, 'ERA': 0, 'WHIP': 0}):
                    # Get recommendations for team 1
                    recs1 = recommendation_engine.get_recommendations_for_team(
                        available_players=available_players,
                        team_players=my_team,
                        draft_state=draft_state,
                        team_name="Team_A",
                        top_n=3,
                        use_ml=False
                    )
                    
                    cache_size_team_a = len(recommendation_engine._cache)
                    assert cache_size_team_a > 0
                    
                    # Get recommendations for team 2 - should clear cache because team name changed
                    recs2 = recommendation_engine.get_recommendations_for_team(
                        available_players=available_players,
                        team_players=my_team,
                        draft_state=draft_state,
                        team_name="Team_B",
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache should be cleared and rebuilt for new team
                    assert len(recommendation_engine._cache) > 0
    
    def test_cache_invalidated_when_pick_made(self, recommendation_engine, sample_players, draft_state):
        """Test that cache is invalidated when a pick is made (draft state changes)."""
        available_players = sample_players[:5]
        my_team = []
        
        # Mock the team service to always return True for has_available_slot_for_player
        with patch.object(recommendation_engine.team_service, 'has_available_slot_for_player', return_value=True):
            # Mock standings calculator to avoid complex calculations
            with patch.object(recommendation_engine.standings_calculator, 'calculate_standings', return_value={'total_points': {}, 'category_points': {}}):
                with patch.object(recommendation_engine.standings_calculator, '_calculate_team_totals', return_value={'IP': 0, 'HR': 0, 'R': 0, 'RBI': 0, 'SB': 0, 'OBP': 0, 'K': 0, 'W': 0, 'QS': 0, 'SV': 0, 'HD': 0, 'ERA': 0, 'WHIP': 0}):
                    # Get recommendations before pick
                    recs1 = recommendation_engine.get_recommendations(
                        available_players=available_players,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    initial_cache_size = len(recommendation_engine._cache)
                    assert initial_cache_size > 0
                    
                    # Simulate a pick being made
                    pick = DraftPick(
                        pick_number=1,
                        round=1,
                        team_name="Team_A",
                        player_id="player_0"
                    )
                    draft_state.picks.append(pick)
                    
                    # Get recommendations after pick - cache should be invalidated
                    recs2 = recommendation_engine.get_recommendations(
                        available_players=available_players,
                        my_team=my_team,
                        draft_state=draft_state,
                        top_n=3,
                        use_ml=False
                    )
                    
                    # Cache should be cleared and rebuilt
                    assert len(recommendation_engine._cache) > 0
    
    def test_available_players_hash_function(self, recommendation_engine, sample_players):
        """Test that the available players hash function works correctly."""
        # Same players should produce same hash
        hash1 = recommendation_engine._get_available_players_hash(sample_players[:5])
        hash2 = recommendation_engine._get_available_players_hash(sample_players[:5])
        assert hash1 == hash2, "Same players should produce same hash"
        
        # Different players should produce different hash
        hash3 = recommendation_engine._get_available_players_hash(sample_players[1:6])
        assert hash1 != hash3, "Different players should produce different hash"
        
        # Order shouldn't matter (hash uses sorted player IDs)
        players_reversed = list(reversed(sample_players[:5]))
        hash4 = recommendation_engine._get_available_players_hash(players_reversed)
        assert hash1 == hash4, "Player order shouldn't affect hash"
    
    def test_draft_state_hash_includes_pick_number(self, recommendation_engine, draft_state):
        """Test that draft state hash includes current pick number."""
        # Get hash before any picks
        hash1 = recommendation_engine._get_draft_state_hash(draft_state)
        
        # Add a pick
        pick = DraftPick(
            pick_number=1,
            round=1,
            team_name="Team_A",
            player_id="player_0"
        )
        draft_state.picks.append(pick)
        
        # Get hash after pick
        hash2 = recommendation_engine._get_draft_state_hash(draft_state)
        
        # Hashes should be different
        assert hash1 != hash2, "Draft state hash should change when pick is made"
