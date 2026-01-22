"""
Tests for bench slot filtering in recommendations.

Verifies that players are not recommended if they would only fill the bench slot
when other starting positions are still available.
"""

import pytest
from src.services.team_service import TeamService
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.models.player import Player
from src.models.draft import DraftState


class TestBenchSlotFiltering:
    """Test suite for bench slot filtering functionality."""
    
    @pytest.fixture
    def team_service(self):
        """Create a team service instance."""
        return TeamService()
    
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
    def sample_players(self, all_players):
        """Get sample players for testing."""
        # Get a few different position players
        catcher = next((p for p in all_players if p.position == 'C'), None)
        outfielder = next((p for p in all_players if p.position == 'OF'), None)
        pitcher = next((p for p in all_players if p.position in ['SP', 'RP', 'P']), None)
        
        return {
            'catcher': catcher,
            'outfielder': outfielder,
            'pitcher': pitcher
        }
    
    def test_has_available_slot_excludes_bench(self, team_service, sample_players):
        """Test that has_available_slot_for_player can exclude bench slots."""
        team_name = "Test_Has_Slot"
        team_service.initialize_team_roster(team_name)
        
        catcher = sample_players['catcher']
        if not catcher:
            pytest.skip("No catcher found in player data")
        
        # Verify roster was created
        roster = team_service.get_team_roster(team_name)
        assert roster is not None
        assert 'positions' in roster
        
        # With empty roster, should have slot with or without bench
        assert team_service.has_available_slot_for_player(team_name, catcher, exclude_bench=False)
        assert team_service.has_available_slot_for_player(team_name, catcher, exclude_bench=True)
    
    def test_bench_only_slot_filtered_when_excluded(self, team_service, all_players):
        """Test that players are filtered when only bench slot is available and exclude_bench=True."""
        team_name = "Test Team"
        team_service.initialize_team_roster(team_name)
        
        # Find a catcher
        catcher = next((p for p in all_players if p.position == 'C'), None)
        if not catcher:
            pytest.skip("No catcher found in player data")
        
        # Fill ALL positions that catcher is eligible for (C, U, BENCH)
        # This way, only BENCH will be available
        roster = team_service.get_team_roster(team_name)
        roster['positions']['C'][0] = {
            'player_id': 'dummy_catcher',
            'name': 'Dummy Catcher',
            'position': 'C'
        }
        roster['positions']['U'][0] = {
            'player_id': 'dummy_utility',
            'name': 'Dummy Utility',
            'position': 'OF'
        }
        
        # Save the modified roster
        import json
        from pathlib import Path
        from src.services.draft_order import DraftOrder
        
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = team_service.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        with open(roster_file, 'w') as f:
            json.dump(roster, f, indent=2)
        
        # Now catcher can only go to BENCH (since C and U are filled)
        # With exclude_bench=False, should have slot (BENCH)
        assert team_service.has_available_slot_for_player(team_name, catcher, exclude_bench=False)
        
        # With exclude_bench=True, should NOT have slot
        assert not team_service.has_available_slot_for_player(team_name, catcher, exclude_bench=True)
    
    def test_recommendations_exclude_bench_only_players(
        self, recommendation_engine, all_players, draft_service
    ):
        """Test that recommendations don't include players that would only fill bench."""
        # Create a draft state with unique team name
        team_name = "Test_Recommendations"
        draft_state = DraftState(
            draft_id="test_bench_filter",
            league_name="Test League",
            total_teams=13,
            roster_size=21,
            my_team_name=team_name,
            current_pick=1,
            current_round=1,
            picks=[],
            team_rosters={team_name: []},
            is_complete=False
        )
        
        # Initialize team roster
        recommendation_engine.team_service.initialize_team_roster(team_name)
        
        # Verify roster was created
        roster = recommendation_engine.team_service.get_team_roster(team_name)
        assert roster is not None
        assert 'positions' in roster
        
        # Get available players
        available_players = all_players[:100]  # Use first 100 for speed
        my_team = []
        
        # Get recommendations
        recommendations = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=draft_state,
            top_n=5,
            use_ml=False
        )
        
        # Verify recommendations are returned
        assert len(recommendations) > 0, "Should have recommendations with empty roster"
        
        # Verify each recommended player has a non-bench slot available
        for rec in recommendations:
            player = rec['player']
            # Should have slot when excluding bench
            has_non_bench_slot = recommendation_engine.team_service.has_available_slot_for_player(
                team_name, player, exclude_bench=True
            )
            assert has_non_bench_slot, f"Player {player.name} ({player.position}) should have non-bench slot"
    
    def test_recommendations_with_nearly_full_roster(
        self, recommendation_engine, all_players, draft_service
    ):
        """Test recommendations when roster is nearly full (only bench slot left)."""
        # Create a draft state
        draft_state = DraftState(
            draft_id="test_nearly_full",
            league_name="Test League",
            total_teams=13,
            roster_size=21,
            my_team_name="Test Team",
            current_pick=20,
            current_round=20,
            picks=[],
            team_rosters={"Test Team": []},
            is_complete=False
        )
        
        # Initialize team roster
        recommendation_engine.team_service.initialize_team_roster("Test Team")
        
        # Fill most positions (leave only BENCH empty)
        roster = recommendation_engine.team_service.get_team_roster("Test Team")
        positions = roster['positions']
        
        # Fill all positions except BENCH
        player_idx = 0
        for pos, slots in positions.items():
            if pos == 'BENCH':
                continue  # Leave bench empty
            for i in range(len(slots)):
                if player_idx < len(all_players):
                    player = all_players[player_idx]
                    positions[pos][i] = {
                        'player_id': player.player_id,
                        'name': player.name,
                        'position': player.position
                    }
                    player_idx += 1
        
        # Save the modified roster
        import json
        from pathlib import Path
        from src.services.draft_order import DraftOrder
        
        team_folder_name = DraftOrder.sanitize_team_name("Test Team")
        team_dir = recommendation_engine.team_service.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        with open(roster_file, 'w') as f:
            json.dump(roster, f, indent=2)
        
        # Get available players (those not on roster)
        drafted_ids = [p.player_id for p in all_players[:player_idx]]
        available_players = [p for p in all_players if p.player_id not in drafted_ids]
        my_team = all_players[:player_idx]
        
        # Get recommendations
        recommendations = recommendation_engine.get_recommendations(
            available_players=available_players,
            my_team=my_team,
            draft_state=draft_state,
            top_n=5,
            use_ml=False
        )
        
        # When only bench is available, recommendations should be empty
        # (because we exclude bench slots in recommendations)
        assert len(recommendations) == 0, "Should not recommend players when only bench slot is available"
    
    def test_eligible_positions_for_different_player_types(self, team_service):
        """Test that eligible positions are correctly determined for different player types."""
        # Test catcher
        catcher = Player(player_id="test_c", name="Test Catcher", position="C", team="TEST")
        eligible = team_service._determine_eligible_positions(catcher)
        assert 'C' in eligible
        assert 'U' in eligible  # Utility
        assert 'BENCH' in eligible
        assert 'P' not in eligible  # Not a pitcher
        
        # Test 2B (eligible for MI)
        second_base = Player(player_id="test_2b", name="Test 2B", position="2B", team="TEST")
        eligible = team_service._determine_eligible_positions(second_base)
        assert '2B' in eligible
        assert 'MI' in eligible  # Middle infielder
        assert 'U' in eligible
        assert 'BENCH' in eligible
        assert 'CI' not in eligible  # Not corner infielder
        
        # Test 1B (eligible for CI)
        first_base = Player(player_id="test_1b", name="Test 1B", position="1B", team="TEST")
        eligible = team_service._determine_eligible_positions(first_base)
        assert '1B' in eligible
        assert 'CI' in eligible  # Corner infielder
        assert 'U' in eligible
        assert 'BENCH' in eligible
        assert 'MI' not in eligible  # Not middle infielder
        
        # Test pitcher
        pitcher = Player(player_id="test_p", name="Test Pitcher", position="SP", team="TEST")
        eligible = team_service._determine_eligible_positions(pitcher)
        assert 'P' in eligible
        assert 'BENCH' in eligible
        assert 'U' not in eligible  # Pitchers can't be utility
        assert 'C' not in eligible
    
    def test_exclude_bench_parameter_default(self, team_service, all_players):
        """Test that exclude_bench parameter defaults to False for backward compatibility."""
        team_name = "Test Team"
        team_service.initialize_team_roster(team_name)
        
        player = all_players[0] if all_players else None
        if not player:
            pytest.skip("No players available")
        
        # Default behavior (exclude_bench not specified) should include bench
        has_slot_default = team_service.has_available_slot_for_player(team_name, player)
        has_slot_explicit_false = team_service.has_available_slot_for_player(team_name, player, exclude_bench=False)
        
        # Both should be the same (backward compatible)
        assert has_slot_default == has_slot_explicit_false
