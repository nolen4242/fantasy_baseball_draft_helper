"""
Tests for enhanced standings calculator with filtering and sorting.
"""

import pytest
from src.services.standings_calculator_enhanced import StandingsCalculatorEnhanced
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.models.player import Player


class TestStandingsEnhanced:
    """Test suite for enhanced standings calculator."""
    
    @pytest.fixture
    def player_loader(self):
        """Create a master player dict loader instance."""
        return MasterPlayerDictLoader()
    
    @pytest.fixture
    def all_players(self, player_loader):
        """Load all players from master player dict."""
        return player_loader.load_all_players()
    
    @pytest.fixture
    def standings_calc(self):
        """Create an enhanced standings calculator instance."""
        return StandingsCalculatorEnhanced()
    
    @pytest.fixture
    def sample_rosters(self, all_players):
        """Create sample team rosters for testing."""
        # Create 3 teams with different players
        team_a_players = all_players[:7]  # First 7 players
        team_b_players = all_players[7:14]  # Next 7 players
        team_c_players = all_players[14:21]  # Next 7 players
        
        return {
            'Team A': team_a_players,
            'Team B': team_b_players,
            'Team C': team_c_players
        }
    
    def test_individual_stat_rankings(self, standings_calc, sample_rosters):
        """Test getting rankings for individual stats."""
        # Test HR rankings
        hr_rankings = standings_calc.get_individual_stat_rankings(sample_rosters, 'HR')
        
        assert len(hr_rankings) == 3
        assert all('team_name' in r for r in hr_rankings)
        assert all('value' in r for r in hr_rankings)
        assert all('rank' in r for r in hr_rankings)
        
        # Verify ranks are sequential
        ranks = [r['rank'] for r in hr_rankings]
        assert ranks == [1, 2, 3]
    
    def test_individual_stat_rankings_with_limit(self, standings_calc, sample_rosters):
        """Test getting top N rankings."""
        # Get top 2 teams
        top_2 = standings_calc.get_individual_stat_rankings(sample_rosters, 'HR', limit=2)
        
        assert len(top_2) == 2
        assert top_2[0]['rank'] == 1
        assert top_2[1]['rank'] == 2
    
    def test_era_rankings_lower_is_better(self, standings_calc, sample_rosters):
        """Test that ERA rankings treat lower values as better."""
        era_rankings = standings_calc.get_individual_stat_rankings(sample_rosters, 'ERA')
        
        # Verify that teams are sorted by ERA (ascending)
        if len(era_rankings) >= 2:
            # First team should have lower or equal ERA than second
            # (unless below IP minimum)
            first_team = era_rankings[0]
            second_team = era_rankings[1]
            
            if not first_team['below_ip_minimum'] and not second_team['below_ip_minimum']:
                assert first_team['value'] <= second_team['value']
    
    def test_filtered_standings_sort_by_hr(self, standings_calc, sample_rosters):
        """Test filtering standings sorted by HR."""
        filtered = standings_calc.get_filtered_standings(sample_rosters, sort_by='HR')
        
        assert 'final_rankings' in filtered
        assert 'sort_by' in filtered
        assert filtered['sort_by'] == 'HR'
        assert len(filtered['final_rankings']) == 3
    
    def test_filtered_standings_with_min_filter(self, standings_calc, sample_rosters):
        """Test filtering standings with minimum value filter."""
        # Filter teams with at least 50 HR
        filtered = standings_calc.get_filtered_standings(
            sample_rosters,
            filter_category='HR',
            filter_min_value=50.0
        )
        
        assert 'filter_applied' in filtered
        assert filtered['filter_applied'] is True
        
        # Verify all teams meet the minimum
        for team_name in filtered['final_rankings']:
            hr_value = filtered['category_totals'][team_name]['HR']
            assert hr_value >= 50.0
    
    def test_filtered_standings_with_max_filter(self, standings_calc, sample_rosters):
        """Test filtering standings with maximum value filter."""
        # Filter teams with ERA below 4.00
        filtered = standings_calc.get_filtered_standings(
            sample_rosters,
            filter_category='ERA',
            filter_max_value=4.00
        )
        
        assert 'filter_applied' in filtered
        
        # Verify all teams meet the maximum
        for team_name in filtered['final_rankings']:
            era_value = filtered['category_totals'][team_name]['ERA']
            # Only check if team meets IP minimum
            if not filtered['category_totals'][team_name].get('_below_ip_minimum', False):
                assert era_value <= 4.00
    
    def test_category_leaders(self, standings_calc, sample_rosters):
        """Test getting category leaders."""
        # Get top 2 HR leaders
        leaders = standings_calc.get_category_leaders(sample_rosters, 'HR', top_n=2)
        
        assert len(leaders) <= 2
        assert all('team_name' in l for l in leaders)
        assert all('value' in l for l in leaders)
        assert all('rank' in l for l in leaders)
    
    def test_validate_pitching_calculations(self, standings_calc, sample_rosters):
        """Test pitching calculation validation."""
        validation = standings_calc.validate_pitching_calculations(sample_rosters)
        
        assert len(validation) == 3  # 3 teams
        
        for team_name, results in validation.items():
            assert 'total_ip' in results
            assert 'meets_ip_minimum' in results
            assert 'exceeds_ip_maximum' in results
            assert 'team_era' in results
            assert 'team_whip' in results
            assert 'total_k' in results
            assert 'scaled_k' in results
            assert 'pitcher_count' in results
            assert 'pitcher_details' in results
            
            # Verify pitcher details structure
            for pitcher in results['pitcher_details']:
                assert 'name' in pitcher
                assert 'position' in pitcher
                assert 'ip' in pitcher
    
    def test_pitching_ip_minimum_handling(self, standings_calc, all_players):
        """Test that teams below IP minimum are handled correctly."""
        # Create a team with very few pitchers (below IP minimum)
        pitchers = [p for p in all_players if p.position in ['SP', 'RP', 'P']][:2]
        
        team_rosters = {
            'Low IP Team': pitchers
        }
        
        validation = standings_calc.validate_pitching_calculations(team_rosters)
        
        assert 'Low IP Team' in validation
        team_results = validation['Low IP Team']
        
        # Should be below IP minimum with only 2 pitchers
        assert team_results['total_ip'] < 1000.0
        assert team_results['meets_ip_minimum'] is False
    
    def test_pitching_ip_maximum_scaling(self, standings_calc, all_players):
        """Test that teams exceeding IP maximum have stats scaled down."""
        # Create a team with many pitchers (exceeding IP maximum)
        pitchers = [p for p in all_players if p.position in ['SP', 'RP', 'P']][:15]
        
        team_rosters = {
            'High IP Team': pitchers
        }
        
        validation = standings_calc.validate_pitching_calculations(team_rosters)
        
        assert 'High IP Team' in validation
        team_results = validation['High IP Team']
        
        # If exceeds maximum, scaled values should be less than totals
        if team_results['exceeds_ip_maximum']:
            assert team_results['scaled_k'] <= team_results['total_k']
            assert team_results['scaled_wqs'] <= team_results['total_wqs']
    
    def test_standings_calculation_consistency(self, standings_calc, sample_rosters):
        """Test that standings calculations are consistent."""
        # Calculate standings twice
        standings1 = standings_calc.calculate_standings(sample_rosters, use_cache=False)
        standings2 = standings_calc.calculate_standings(sample_rosters, use_cache=False)
        
        # Results should be identical
        assert standings1['final_rankings'] == standings2['final_rankings']
        assert standings1['total_points'] == standings2['total_points']
    
    def test_all_categories_have_rankings(self, standings_calc, sample_rosters):
        """Test that all categories have rankings."""
        standings = standings_calc.calculate_standings(sample_rosters)
        
        all_categories = standings_calc.BATTING_CATEGORIES + standings_calc.PITCHING_CATEGORIES
        
        for category in all_categories:
            assert category in standings['category_rankings']
            assert len(standings['category_rankings'][category]) == 3
    
    def test_category_points_sum_correctly(self, standings_calc, sample_rosters):
        """Test that category points sum to total points."""
        standings = standings_calc.calculate_standings(sample_rosters)
        
        for team_name in sample_rosters.keys():
            # Sum category points
            category_sum = 0
            for category in standings_calc.BATTING_CATEGORIES + standings_calc.PITCHING_CATEGORIES:
                category_sum += standings['category_points'][category].get(team_name, 0)
            
            # Should equal total points
            total = standings['total_points'][team_name]
            assert abs(category_sum - total) < 0.01  # Allow small floating point error
