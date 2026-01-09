"""Data cleaning and validation service."""
from typing import List, Dict, Optional
from src.models.player import Player
from src.services.player_matcher import PlayerMatcher


class DataCleaner:
    """
    Cleans and validates player data.
    Ensures data integrity and flags issues.
    """
    
    def __init__(self):
        self.player_matcher = PlayerMatcher()
    
    def clean_and_validate_players(self, players: List[Player]) -> Dict:
        """
        Clean and validate player data.
        
        Returns:
            Dict with:
            - cleaned_players: List of cleaned Player objects
            - issues: List of data quality issues
            - statistics: Data quality statistics
        """
        issues = []
        statistics = {
            'total_players': len(players),
            'players_with_complete_data': 0,
            'players_with_missing_data': 0,
            'players_with_invalid_data': 0,
            'duplicates_found': 0,
        }
        
        cleaned_players = []
        seen_names = set()
        
        for player in players:
            # Check for duplicates
            normalized_name = self.player_matcher.normalize_player_name(player.name)
            if normalized_name in seen_names:
                statistics['duplicates_found'] += 1
                issues.append({
                    'type': 'duplicate',
                    'player': player.name,
                    'severity': 'warning',
                    'message': f'Duplicate player found: {player.name}'
                })
                continue
            seen_names.add(normalized_name)
            
            # Validate required fields
            validation_result = self.validate_player(player)
            if not validation_result['is_valid']:
                statistics['players_with_invalid_data'] += 1
                issues.extend(validation_result['issues'])
                # Still add player, but flag issues
            else:
                statistics['players_with_complete_data'] += 1
            
            # Check data completeness
            completeness = self.calculate_data_completeness(player)
            if completeness < 0.5:
                statistics['players_with_missing_data'] += 1
                issues.append({
                    'type': 'incomplete_data',
                    'player': player.name,
                    'severity': 'warning',
                    'message': f'{player.name} has {completeness*100:.0f}% data completeness',
                    'completeness': completeness
                })
            
            # Clean player data
            cleaned_player = self.clean_player(player)
            cleaned_players.append(cleaned_player)
        
        return {
            'cleaned_players': cleaned_players,
            'issues': issues,
            'statistics': statistics
        }
    
    def validate_player(self, player: Player) -> Dict:
        """
        Validate a player object.
        
        Returns:
            Dict with 'is_valid' bool and 'issues' list
        """
        issues = []
        
        # Required fields
        if not player.name or not player.name.strip():
            issues.append({
                'type': 'missing_name',
                'severity': 'error',
                'message': 'Player missing name'
            })
        
        if not player.position:
            issues.append({
                'type': 'missing_position',
                'severity': 'error',
                'message': f'{player.name} missing position'
            })
        
        # Validate stats are reasonable
        if player.position not in ['SP', 'RP', 'P']:
            # Hitter validation
            if player.projected_home_runs and player.projected_home_runs > 80:
                issues.append({
                    'type': 'outlier',
                    'severity': 'warning',
                    'message': f'{player.name} has unusually high HR projection: {player.projected_home_runs}'
                })
            
            if player.projected_obp and (player.projected_obp < 0.200 or player.projected_obp > 0.500):
                issues.append({
                    'type': 'outlier',
                    'severity': 'warning',
                    'message': f'{player.name} has unusual OBP: {player.projected_obp}'
                })
        else:
            # Pitcher validation
            if player.projected_era and (player.projected_era < 0.50 or player.projected_era > 8.00):
                issues.append({
                    'type': 'outlier',
                    'severity': 'warning',
                    'message': f'{player.name} has unusual ERA: {player.projected_era}'
                })
            
            if player.projected_whip and (player.projected_whip < 0.50 or player.projected_whip > 2.00):
                issues.append({
                    'type': 'outlier',
                    'severity': 'warning',
                    'message': f'{player.name} has unusual WHIP: {player.projected_whip}'
                })
        
        return {
            'is_valid': len([i for i in issues if i['severity'] == 'error']) == 0,
            'issues': issues
        }
    
    def calculate_data_completeness(self, player: Player) -> float:
        """
        Calculate data completeness score (0.0 to 1.0).
        
        Returns:
            Completeness score
        """
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        if is_pitcher:
            required_fields = [
                'projected_era', 'projected_strikeouts', 'projected_whip',
                'projected_wins', 'projected_saves'
            ]
        else:
            required_fields = [
                'projected_home_runs', 'projected_obp', 'projected_runs',
                'projected_rbi', 'projected_stolen_bases'
            ]
        
        filled = sum(1 for field in required_fields if getattr(player, field) is not None)
        return filled / len(required_fields) if required_fields else 0.0
    
    def clean_player(self, player: Player) -> Player:
        """
        Clean a player object (normalize values, fix common issues).
        
        Returns:
            Cleaned Player object
        """
        # Normalize name
        if player.name:
            player.name = player.name.strip()
        
        # Normalize team
        if player.team:
            player.team = player.team.strip().upper()
        
        # Ensure position eligibility is set
        if not hasattr(player, 'position_eligibility') or not player.position_eligibility:
            player.position_eligibility = [player.position] if player.position else []
        
        # Normalize position eligibility
        if player.position_eligibility:
            player.position_eligibility = [p.strip().upper() for p in player.position_eligibility if p]
        
        return player
    
    def find_cross_database_matches(
        self,
        players_by_source: Dict[str, List[Player]]
    ) -> Dict[str, List[Dict]]:
        """
        Find potential matches across databases that need confirmation.
        
        Args:
            players_by_source: Dict mapping source name to list of players
        
        Returns:
            Dict mapping player_id to list of potential matches with confidence scores
        """
        match_report = {}
        
        # Convert to dict format for matcher
        all_players_dict = []
        for source, players in players_by_source.items():
            for player in players:
                all_players_dict.append({
                    'player_id': player.player_id,
                    'name': player.name,
                    'source': source
                })
        
        # Find matches for each player
        for source, players in players_by_source.items():
            for player in players:
                matches = self.player_matcher.find_matches(
                    player_name=player.name,
                    player_source=source,
                    candidate_players=all_players_dict,
                    min_confidence=0.70
                )
                
                # Only include matches that need confirmation (confidence < 0.95)
                needs_confirmation = [
                    {
                        'player_id': m.player_id,
                        'name': m.name,
                        'source': m.source,
                        'confidence': m.confidence,
                        'reason': m.match_reason
                    }
                    for m in matches if m.confidence < 0.95
                ]
                
                if needs_confirmation:
                    match_report[player.player_id] = needs_confirmation
        
        return match_report



