"""
Tests for draft board API endpoint.
"""

import pytest
import json
from src.api.app import app
from src.services.draft_service import DraftService
from src.services.team_service import TeamService
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.models.draft import DraftState


class TestDraftBoard:
    """Test suite for draft board functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def player_loader(self):
        """Create a master player dict loader instance."""
        return MasterPlayerDictLoader()
    
    @pytest.fixture
    def all_players(self, player_loader):
        """Load all players from master player dict."""
        return player_loader.load_all_players()
    
    @pytest.fixture
    def draft_service_instance(self):
        """Create a draft service instance."""
        return DraftService()
    
    @pytest.fixture
    def team_service(self):
        """Create a team service instance."""
        return TeamService()
    
    @pytest.fixture
    def sample_draft(self, draft_service_instance, all_players, team_service):
        """Create a sample draft with some picks."""
        # Create draft
        draft = draft_service_instance.create_draft(
            draft_id="test_board_draft",
            league_name="Test League",
            total_teams=3,
            roster_size=21,
            my_team_name="Team A"
        )
        
        # Initialize team rosters
        for team_name in ["Team A", "Team B", "Team C"]:
            team_service.initialize_team_roster(team_name)
        
        # Make a few picks
        if len(all_players) >= 3:
            # Team A picks first player
            draft_service_instance.draft_player(
                player_id=all_players[0].player_id,
                team_name="Team A",
                player=all_players[0]
            )
            
            # Team B picks second player
            draft_service_instance.draft_player(
                player_id=all_players[1].player_id,
                team_name="Team B",
                player=all_players[1]
            )
            
            # Team C picks third player
            draft_service_instance.draft_player(
                player_id=all_players[2].player_id,
                team_name="Team C",
                player=all_players[2]
            )
        
        return draft
    
    def test_draft_board_no_active_draft(self, client):
        """Test draft board endpoint with no active draft."""
        # Ensure no active draft
        from src.api.app import draft_service
        draft_service.current_draft = None
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['success'] is False
        assert 'No active draft' in data['message']
    
    def test_draft_board_with_active_draft(self, client, sample_draft, all_players):
        """Test draft board endpoint with active draft."""
        # Set the active draft
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        # Also set all_players in the app module
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert 'board' in data
        
        board = data['board']
        assert 'teams' in board
        assert 'position_slots' in board
        assert 'current_pick' in board
        assert 'current_round' in board
        assert 'my_team' in board
        
        # Verify teams (should have all teams from draft)
        assert len(board['teams']) > 0
        
        # Verify each team has required fields
        for team in board['teams']:
            assert 'name' in team
            assert 'color' in team
            assert 'player_count' in team
            assert 'positions' in team
            assert 'is_my_team' in team
    
    def test_draft_board_position_slots(self, client, sample_draft, all_players):
        """Test that draft board includes all position slots."""
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        board = data['board']
        position_slots = board['position_slots']
        
        # Verify all expected positions are present
        expected_positions = ['C', '1B', '2B', '3B', 'SS', 'MI', 'CI', 
                            'OF1', 'OF2', 'OF3', 'OF4', 'U',
                            'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9',
                            'BENCH']
        
        for pos in expected_positions:
            assert pos in position_slots
    
    def test_draft_board_player_positions(self, client, sample_draft, all_players):
        """Test that drafted players appear in position slots."""
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        board = data['board']
        
        # At least one team should have players
        has_players = False
        for team in board['teams']:
            if team['player_count'] > 0:
                has_players = True
                # Verify positions dict exists and has entries
                assert isinstance(team['positions'], dict)
                if len(team['positions']) > 0:
                    # Check structure of position entry
                    for pos_key, player_data in team['positions'].items():
                        assert 'player_id' in player_data
                        assert 'name' in player_data
                        assert 'position' in player_data
        
        assert has_players, "At least one team should have players"
    
    def test_draft_board_my_team_flag(self, client, sample_draft, all_players):
        """Test that my_team flag is set correctly."""
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        board = data['board']
        
        # Verify exactly one team is marked as my_team
        my_teams = [team for team in board['teams'] if team['is_my_team']]
        assert len(my_teams) == 1
        assert my_teams[0]['name'] == "Team A"
    
    def test_draft_board_team_colors(self, client, sample_draft, all_players):
        """Test that teams have color assignments."""
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        board = data['board']
        
        # Verify all teams have colors
        for team in board['teams']:
            assert 'color' in team
            assert team['color'].startswith('#')
            assert len(team['color']) == 7  # #RRGGBB format
    
    def test_draft_board_current_pick_info(self, client, sample_draft, all_players):
        """Test that current pick information is correct."""
        from src.api.app import draft_service
        draft_service.current_draft = sample_draft
        
        import src.api.app as app_module
        app_module.all_players = all_players
        
        response = client.get('/api/draft/board')
        data = json.loads(response.data)
        
        board = data['board']
        
        # Verify current pick info
        assert board['current_pick'] > 0
        assert board['current_round'] > 0
        assert board['my_team'] == "Team A"
