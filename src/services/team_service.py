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
        'P': 9    # Pitchers (any combination of SP/RP)
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
        
        return eligible
    
    def _find_empty_slot(self, positions: Dict, eligible_positions: List[str]) -> Optional[tuple]:
        """Find the first empty slot in eligible positions."""
        # Priority order: specific positions first, then flexible
        priority_order = ['C', '1B', '2B', '3B', 'SS', 'OF', 'P', 'MI', 'CI', 'U']
        
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
        
        # Save updated roster
        with open(roster_file, 'w', encoding='utf-8') as f:
            json.dump(roster, f, indent=2)
    
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

