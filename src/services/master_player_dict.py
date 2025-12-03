"""Master player dictionary service for merging projections."""
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional
from src.models.player import Player


class MasterPlayerDict:
    """Manages master player dictionary with merged projections."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
        self.data_dir = Path(data_dir)
        self.batters_dir = self.data_dir / "batters"
        self.pitchers_dir = self.data_dir / "pitchers"
        self.batters_dir.mkdir(parents=True, exist_ok=True)
        self.pitchers_dir.mkdir(parents=True, exist_ok=True)
        
        self.batters_master_file = self.batters_dir / "master_players.json"
        self.pitchers_master_file = self.pitchers_dir / "master_players.json"
    
    def normalize_player_name(self, name: str) -> str:
        """Normalize player name for matching (lowercase, remove special chars, handle suffixes)."""
        import re
        import unicodedata
        
        # Remove accents/diacritics for better matching
        normalized = unicodedata.normalize('NFD', name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        
        normalized = normalized.lower().strip()
        # Remove Jr., Sr., II, III, IV, etc.
        normalized = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv|v|2nd|3rd|4th)$', '', normalized)
        # Remove periods, apostrophes, hyphens
        normalized = normalized.replace(".", "").replace("'", "").replace("-", " ")
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def load_master_dict(self, player_type: str = "batters") -> Dict[str, Dict]:
        """Load master player dictionary from file."""
        master_file = self.batters_master_file if player_type == "batters" else self.pitchers_master_file
        
        if not master_file.exists():
            return {}
        
        with open(master_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_master_dict(self, master_dict: Dict[str, Dict], player_type: str = "batters"):
        """Save master player dictionary to file."""
        master_file = self.batters_master_file if player_type == "batters" else self.pitchers_master_file
        
        with open(master_file, 'w', encoding='utf-8') as f:
            json.dump(master_dict, f, indent=2)
    
    def merge_steamer_projections(self, players: List[Player], player_type: str = "batters"):
        """
        Merge Steamer projections into master dictionary.
        
        Args:
            players: List of Player objects from Steamer
            player_type: "batters" or "pitchers"
        """
        master_dict = self.load_master_dict(player_type)
        
        for player in players:
            normalized_name = self.normalize_player_name(player.name)
            
            if normalized_name not in master_dict:
                # Create new entry
                master_dict[normalized_name] = {
                    'name': player.name,
                    'normalized_name': normalized_name,
                    'projections': {}
                }
            
            # Merge Steamer projections
            if 'steamer' not in master_dict[normalized_name]['projections']:
                master_dict[normalized_name]['projections']['steamer'] = {}
            
            # Store only relevant stats based on player type
            if player_type == "batters":
                # Only store batting stats for batters
                master_dict[normalized_name]['projections']['steamer'] = {
                    'position': player.position,
                    'team': player.team,
                    'age': player.age,
                    'projected_home_runs': player.projected_home_runs,
                    'projected_obp': player.projected_obp,
                    'projected_runs': player.projected_runs,
                    'projected_rbi': player.projected_rbi,
                    'projected_stolen_bases': player.projected_stolen_bases,
                }
            else:
                # Only store pitching stats for pitchers
                master_dict[normalized_name]['projections']['steamer'] = {
                    'position': player.position,
                    'team': player.team,
                    'age': player.age,
                    'projected_wins': player.projected_wins,
                    'projected_quality_starts': player.projected_quality_starts,
                    'projected_strikeouts': player.projected_strikeouts,
                    'projected_era': player.projected_era,
                    'projected_whip': player.projected_whip,
                    'projected_saves': player.projected_saves,
                    'projected_holds': player.projected_holds,
                }
            
            # Update primary name if this is a better match
            if player.name and player.name != master_dict[normalized_name]['name']:
                # Keep the most recent or most complete name
                if len(player.name) > len(master_dict[normalized_name]['name']):
                    master_dict[normalized_name]['name'] = player.name
        
        self.save_master_dict(master_dict, player_type)
        return master_dict
    
    def merge_cbs_data(self, players: List[Player], player_type: str = "batters"):
        """
        Merge CBS data into master dictionary.
        CBS data is the source of truth for available players.
        
        Args:
            players: List of Player objects from CBS
            player_type: "batters" or "pitchers"
        """
        master_dict = self.load_master_dict(player_type)
        
        for player in players:
            normalized_name = self.normalize_player_name(player.name)
            
            if normalized_name not in master_dict:
                # Create new entry
                master_dict[normalized_name] = {
                    'name': player.name,
                    'normalized_name': normalized_name,
                    'projections': {},
                    'cbs_data': {}
                }
            
            # Store CBS data (source of truth for availability)
            master_dict[normalized_name]['cbs_data'] = {
                'name': player.name,
                'position': player.position,
                'team': player.team,
                'age': player.age,
                'player_id': player.player_id,
                # Include any CBS-specific fields
            }
            
            # Update primary name from CBS (CBS is authoritative)
            master_dict[normalized_name]['name'] = player.name
        
        self.save_master_dict(master_dict, player_type)
        return master_dict
    
    def load_adp_data(self):
        """Load ADP data from CSV and merge into master dictionaries."""
        adp_file = self.data_dir / "adp.csv"
        
        if not adp_file.exists():
            return
        
        # Load ADP data into a dictionary keyed by normalized name
        adp_dict = {}
        
        with open(adp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                player_name = row.get('Player Name', '').strip()
                if not player_name:
                    continue
                
                # Parse name and team from format like "Aaron Judge (NYY)"
                name = player_name
                team = None
                if '(' in player_name and ')' in player_name:
                    parts = player_name.rsplit('(', 1)
                    name = parts[0].strip()
                    team = parts[1].rstrip(')').strip()
                
                # Get ADP value (AVG. column)
                adp_str = row.get('AVG.', '').strip()
                try:
                    adp = float(adp_str) if adp_str else None
                except (ValueError, TypeError):
                    adp = None
                
                if adp is not None:
                    normalized_name = self.normalize_player_name(name)
                    adp_dict[normalized_name] = adp
        
        # Merge ADP into both batters and pitchers master dictionaries
        for player_type in ['batters', 'pitchers']:
            master_dict = self.load_master_dict(player_type)
            updated = False
            
            for normalized_name, player_data in master_dict.items():
                if normalized_name in adp_dict:
                    player_data['adp'] = adp_dict[normalized_name]
                    updated = True
            
            if updated:
                self.save_master_dict(master_dict, player_type)
        
        # Apply custom ADP overrides for specific players/positions
        self._apply_adp_overrides()
    
    def _apply_adp_overrides(self):
        """Apply custom ADP overrides for specific players."""
        # Custom ADP overrides: (normalized_name, player_type, adp_value)
        overrides = [
            ('shohei ohtani', 'pitchers', 77.0),  # Shohei Ohtani pitcher ADP = 77
        ]
        
        for normalized_name, player_type, adp_value in overrides:
            master_dict = self.load_master_dict(player_type)
            if normalized_name in master_dict:
                master_dict[normalized_name]['adp'] = adp_value
                self.save_master_dict(master_dict, player_type)
    
    def get_players_with_projections(self, player_type: str = "batters") -> List[Player]:
        """
        Get list of players with merged projections.
        Uses CBS data as base, merges in projections.
        
        Args:
            player_type: "batters" or "pitchers"
        
        Returns:
            List of Player objects with merged data
        """
        master_dict = self.load_master_dict(player_type)
        players = []
        
        for normalized_name, player_data in master_dict.items():
            # Start with CBS data as base
            cbs_data = player_data.get('cbs_data', {})
            if not cbs_data:
                continue  # Skip if no CBS data (not available to draft)
            
            # Get best available projections (prefer Steamer for now)
            projections = player_data.get('projections', {})
            steamer = projections.get('steamer', {})
            
            # Get ADP if available
            adp = player_data.get('adp')
            
            # Merge data: CBS base + Steamer projections
            # Only use relevant stats based on player type
            if player_type == "batters":
                player = Player(
                    player_id=cbs_data.get('player_id', normalized_name),
                    name=cbs_data.get('name', player_data['name']),
                    position=cbs_data.get('position') or steamer.get('position') or '',
                    team=cbs_data.get('team') or steamer.get('team') or '',
                    age=cbs_data.get('age') or steamer.get('age'),
                    # Batting stats only
                    projected_home_runs=steamer.get('projected_home_runs'),
                    projected_obp=steamer.get('projected_obp'),
                    projected_runs=steamer.get('projected_runs'),
                    projected_rbi=steamer.get('projected_rbi'),
                    projected_stolen_bases=steamer.get('projected_stolen_bases'),
                    adp=adp,
                )
            else:
                player = Player(
                    player_id=cbs_data.get('player_id', normalized_name),
                    name=cbs_data.get('name', player_data['name']),
                    position=cbs_data.get('position') or steamer.get('position') or '',
                    team=cbs_data.get('team') or steamer.get('team') or '',
                    age=cbs_data.get('age') or steamer.get('age'),
                    # Pitching stats only
                    projected_wins=steamer.get('projected_wins'),
                    projected_quality_starts=steamer.get('projected_quality_starts'),
                    projected_strikeouts=steamer.get('projected_strikeouts'),
                    projected_era=steamer.get('projected_era'),
                    projected_whip=steamer.get('projected_whip'),
                    projected_saves=steamer.get('projected_saves'),
                    projected_holds=steamer.get('projected_holds'),
                    adp=adp,
                )
            players.append(player)
        
        return players
    
    def merge_future_projections(self, players: List[Player], projection_source: str, player_type: str = "batters"):
        """
        Merge future projection sources into master dictionary.
        
        Args:
            players: List of Player objects from new projection source
            projection_source: Name of projection source (e.g., "zips", "thebat", etc.)
            player_type: "batters" or "pitchers"
        """
        master_dict = self.load_master_dict(player_type)
        
        for player in players:
            normalized_name = self.normalize_player_name(player.name)
            
            if normalized_name not in master_dict:
                # Create new entry
                master_dict[normalized_name] = {
                    'name': player.name,
                    'normalized_name': normalized_name,
                    'projections': {}
                }
            
            # Store projections from this source
            if projection_source not in master_dict[normalized_name]['projections']:
                master_dict[normalized_name]['projections'][projection_source] = {}
            
            # Store only relevant stats based on player type
            if player_type == "batters":
                # Only store batting stats for batters
                master_dict[normalized_name]['projections'][projection_source] = {
                    'position': player.position,
                    'team': player.team,
                    'age': player.age,
                    'projected_home_runs': player.projected_home_runs,
                    'projected_obp': player.projected_obp,
                    'projected_runs': player.projected_runs,
                    'projected_rbi': player.projected_rbi,
                    'projected_stolen_bases': player.projected_stolen_bases,
                }
            else:
                # Only store pitching stats for pitchers
                master_dict[normalized_name]['projections'][projection_source] = {
                    'position': player.position,
                    'team': player.team,
                    'age': player.age,
                    'projected_wins': player.projected_wins,
                    'projected_quality_starts': player.projected_quality_starts,
                    'projected_strikeouts': player.projected_strikeouts,
                    'projected_era': player.projected_era,
                    'projected_whip': player.projected_whip,
                    'projected_saves': player.projected_saves,
                    'projected_holds': player.projected_holds,
                }
        
        self.save_master_dict(master_dict, player_type)
        return master_dict

