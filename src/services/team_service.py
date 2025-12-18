"""Service for managing team rosters and picks."""
import json
from pathlib import Path
from typing import List, Optional, Dict
from src.models.player import Player
from src.models.draft import DraftState
from src.services.draft_order import DraftOrder


class TeamService:
    """Manages individual team rosters and their picks."""
    
    # Position requirements for each team
    POSITION_REQUIREMENTS = {
        'C': 1,
        '1B': 1,
        '2B': 1,
        '3B': 1,
        'SS': 1,
        'MI': 1,  # Middle Infielder (2B or SS)
        'CI': 1,  # Corner Infielder (1B or 3B)
        'OF': 4,  # Outfielders
        'U': 1,   # Utility (any offensive position)
        'P': 9,   # Pitchers (any combination of SP/RP)
        'BENCH': 1  # Bench/Reserve (any player - hitter or pitcher)
    }
    
    def __init__(self, teams_dir: str = None):
        if teams_dir is None:
            project_root = Path(__file__).parent.parent.parent
            teams_dir = project_root / "data" / "teams"
        self.teams_dir = Path(teams_dir)
        self.teams_dir.mkdir(parents=True, exist_ok=True)
    
    def save_team_pick(self, team_name: str, player: Player, pick_info: Dict):
        """
        Save a player pick to a team's folder.
        
        Args:
            team_name: Team name
            player: Player object
            pick_info: Dictionary with pick details (round, pick_number, etc.)
        """
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        team_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a file for this pick
        pick_file = team_dir / f"pick_{pick_info.get('pick_number', 0)}.json"
        
        pick_data = {
            'player': player.to_dict(),
            'pick_info': pick_info,
            'position': player.position
        }
        
        with open(pick_file, 'w', encoding='utf-8') as f:
            json.dump(pick_data, f, indent=2)
        
        # Also update the team roster summary
        self._update_team_roster_summary(team_name, player, pick_info)
    
    def _get_empty_position_structure(self) -> Dict:
        """Get empty position structure for a new roster."""
        positions = {}
        for pos, count in self.POSITION_REQUIREMENTS.items():
            positions[pos] = [None] * count
        return positions
    
    def _determine_eligible_positions(self, player: Player) -> List[str]:
        """Determine which roster positions a player is eligible for."""
        eligible = []
        player_pos = player.position.upper()
        
        # Direct position matches
        if player_pos in ['C', '1B', '2B', '3B', 'SS', 'OF']:
            eligible.append(player_pos)
        
        # Pitcher positions
        if player_pos in ['SP', 'RP', 'P']:
            eligible.append('P')
        
        # Flexible positions
        if player_pos in ['2B', 'SS']:
            eligible.append('MI')
        if player_pos in ['1B', '3B']:
            eligible.append('CI')
        
        # Utility can be any offensive position (not pitcher)
        if player_pos not in ['SP', 'RP', 'P']:
            eligible.append('U')
        
        # Bench can be any player (hitter or pitcher)
        eligible.append('BENCH')
        
        return eligible
    
    def _find_empty_slot(self, positions: Dict, eligible_positions: List[str]) -> Optional[tuple]:
        """Find the first empty slot in eligible positions."""
        # Priority order: specific positions first, then flexible, then bench
        priority_order = ['C', '1B', '2B', '3B', 'SS', 'OF', 'P', 'MI', 'CI', 'U', 'BENCH']
        
        for pos in priority_order:
            if pos in eligible_positions and pos in positions:
                for i, slot in enumerate(positions[pos]):
                    if slot is None:
                        return (pos, i)
        
        return None
    
    def _update_team_roster_summary(self, team_name: str, player: Player, pick_info: Dict):
        """Update the team's roster summary file with position-based structure."""
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        
        # Load existing roster or create new
        if roster_file.exists():
            with open(roster_file, 'r', encoding='utf-8') as f:
                roster = json.load(f)
        else:
            roster = {
                'team_name': team_name,
                'positions': self._get_empty_position_structure(),
                'all_players': []  # Keep full list for backwards compatibility
            }
        
        # Ensure positions structure exists
        if 'positions' not in roster:
            roster['positions'] = self._get_empty_position_structure()
        
        # Create player entry
        player_entry = {
            'player_id': player.player_id,
            'name': player.name,
            'position': player.position,
            'team': player.team,
            'pick_number': pick_info.get('pick_number'),
            'round': pick_info.get('round'),
            'stats': {
                'projected_home_runs': player.projected_home_runs,
                'projected_obp': player.projected_obp,
                'projected_runs': player.projected_runs,
                'projected_rbi': player.projected_rbi,
                'projected_stolen_bases': player.projected_stolen_bases,
                'projected_wins': player.projected_wins,
                'projected_quality_starts': player.projected_quality_starts,
                'projected_strikeouts': player.projected_strikeouts,
                'projected_era': player.projected_era,
                'projected_whip': player.projected_whip,
                'projected_saves': player.projected_saves,
                'projected_holds': player.projected_holds,
            }
        }
        
        # Check if player already exists in roster (prevent duplicates)
        existing_player_ids = set()
        for pos_list in roster['positions'].values():
            for slot in pos_list:
                if slot and slot.get('player_id'):
                    existing_player_ids.add(slot['player_id'])
        
        # Check all_players for duplicates too
        if 'all_players' in roster:
            for p in roster['all_players']:
                if p and p.get('player_id'):
                    existing_player_ids.add(p['player_id'])
        
        # Only add if player doesn't already exist
        if player.player_id in existing_player_ids:
            # Player already exists - don't add duplicate
            return
        
        # Add to all_players list (for backwards compatibility)
        if 'all_players' not in roster:
            roster['all_players'] = []
        roster['all_players'].append(player_entry)
        
        # Find eligible positions and fill first available slot
        eligible_positions = self._determine_eligible_positions(player)
        slot = self._find_empty_slot(roster['positions'], eligible_positions)
        
        if slot:
            pos, index = slot
            roster['positions'][pos][index] = player_entry
        else:
            # If no slot found, add to overflow (shouldn't happen in normal draft)
            if 'overflow' not in roster:
                roster['overflow'] = []
            roster['overflow'].append(player_entry)
        
        # Save updated roster (always save, regardless of slot found or not)
        with open(roster_file, 'w', encoding='utf-8') as f:
            json.dump(roster, f, indent=2)
    
    def move_player_position(
        self,
        team_name: str,
        player_id: str,
        from_position: str,
        from_index: int,
        to_position: str,
        to_index: int
    ) -> bool:
        """
        Move a player from one position slot to another.
        
        Args:
            team_name: Team name
            player_id: Player ID to move
            from_position: Source position (e.g., 'OF')
            from_index: Source slot index (0-based)
            to_position: Target position (e.g., 'U')
            to_index: Target slot index (0-based)
        
        Returns:
            True if move was successful, False otherwise
        """
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        
        if not roster_file.exists():
            return False
        
        with open(roster_file, 'r', encoding='utf-8') as f:
            roster = json.load(f)
        
        # Ensure positions structure exists
        if 'positions' not in roster:
            roster['positions'] = self._get_empty_position_structure()
        
        positions = roster['positions']
        
        # Validate positions exist
        if from_position not in positions or to_position not in positions:
            return False
        
        # Validate indices
        if (from_index < 0 or from_index >= len(positions[from_position]) or
            to_index < 0 or to_index >= len(positions[to_position])):
            return False
        
        # Get the player from source position
        source_slot = positions[from_position][from_index]
        if not source_slot or source_slot.get('player_id') != player_id:
            return False
        
        # Check if target slot is empty
        target_slot = positions[to_position][to_index]
        if target_slot is not None:
            return False  # Target slot must be empty
        
        # Move the player
        positions[from_position][from_index] = None
        positions[to_position][to_index] = source_slot
        
        # Save updated roster
        with open(roster_file, 'w', encoding='utf-8') as f:
            json.dump(roster, f, indent=2)
        
        return True
    
    def get_team_roster(self, team_name: str) -> Dict:
        """Get a team's roster with position structure."""
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        
        if not roster_file.exists():
            return {
                'team_name': team_name,
                'positions': self._get_empty_position_structure(),
                'all_players': []
            }
        
        with open(roster_file, 'r', encoding='utf-8') as f:
            roster = json.load(f)
        
        # Ensure positions structure exists
        if 'positions' not in roster:
            roster['positions'] = self._get_empty_position_structure()
        
        # Ensure all_players exists for backwards compatibility
        if 'all_players' not in roster:
            # Rebuild from positions if needed
            all_players = []
            for pos, players in roster.get('positions', {}).items():
                for player in players:
                    if player is not None:
                        all_players.append(player)
            roster['all_players'] = all_players
        
        return roster
    
    def get_team_roster_flat(self, team_name: str) -> List[Dict]:
        """Get a team's roster as a flat list (for backwards compatibility)."""
        roster = self.get_team_roster(team_name)
        return roster.get('all_players', [])
    
    def get_all_team_rosters(self) -> Dict[str, Dict]:
        """Get rosters for all teams with position structure."""
        rosters = {}
        for team_name in DraftOrder.get_all_teams():
            rosters[team_name] = self.get_team_roster(team_name)
        return rosters
    
    def initialize_team_roster(self, team_name: str):
        """Initialize a team's roster file with empty position structure."""
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        team_dir.mkdir(parents=True, exist_ok=True)
        roster_file = team_dir / "roster.json"
        
        if not roster_file.exists():
            roster = {
                'team_name': team_name,
                'positions': self._get_empty_position_structure(),
                'all_players': []
            }
            with open(roster_file, 'w', encoding='utf-8') as f:
                json.dump(roster, f, indent=2)
    
    def cleanup_duplicate_players(self, team_name: str):
        """
        Remove duplicate player entries from a team's roster.
        Keeps the first occurrence of each player and removes duplicates.
        """
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        roster_file = team_dir / "roster.json"
        
        if not roster_file.exists():
            return
        
        with open(roster_file, 'r', encoding='utf-8') as f:
            roster = json.load(f)
        
        if 'positions' not in roster:
            return
        
        # Track which players we've seen
        seen_player_ids = set()
        positions = roster['positions']
        
        # Clean up position slots - remove duplicates
        for pos, slots in positions.items():
            for i, slot in enumerate(slots):
                if slot and slot.get('player_id'):
                    player_id = slot['player_id']
                    if player_id in seen_player_ids:
                        # Duplicate found - remove it
                        positions[pos][i] = None
                    else:
                        seen_player_ids.add(player_id)
        
        # Clean up all_players list - keep only unique players
        if 'all_players' in roster:
            seen_in_all = set()
            unique_players = []
            for player in roster['all_players']:
                player_id = player.get('player_id')
                if player_id and player_id not in seen_in_all:
                    unique_players.append(player)
                    seen_in_all.add(player_id)
            roster['all_players'] = unique_players
        
        # Save cleaned roster
        with open(roster_file, 'w', encoding='utf-8') as f:
            json.dump(roster, f, indent=2)
    
    def remove_team_pick(self, team_name: str, pick_number: int):
        """Remove a pick from a team's roster."""
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        
        # Delete the pick file
        pick_file = team_dir / f"pick_{pick_number}.json"
        if pick_file.exists():
            pick_file.unlink()
        
        # Update the roster.json file
        roster_file = team_dir / "roster.json"
        if roster_file.exists():
            with open(roster_file, 'r', encoding='utf-8') as f:
                roster = json.load(f)
            
            # Remove from all_players
            if 'all_players' in roster:
                roster['all_players'] = [
                    p for p in roster['all_players'] 
                    if p.get('pick_number') != pick_number
                ]
            
            # Remove from positions
            if 'positions' in roster:
                for pos, players in roster['positions'].items():
                    for i, player in enumerate(players):
                        if player is not None and player.get('pick_number') == pick_number:
                            roster['positions'][pos][i] = None
            
            # Remove from overflow if present
            if 'overflow' in roster:
                roster['overflow'] = [
                    p for p in roster['overflow']
                    if p.get('pick_number') != pick_number
                ]
            
            # Save updated roster
            with open(roster_file, 'w', encoding='utf-8') as f:
                json.dump(roster, f, indent=2)

