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
                    'projected_innings_pitched': player.projected_innings_pitched,
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
        """Load ADP data and merge into master dictionaries.

        Supports two formats:
        - NFBC TSV (adp_nfbc.tsv): Tab-separated, 'Player' column as 'Last, First', 'ADP' column
        - Legacy CSV (adp.csv): Comma-separated, 'Player Name' as 'First Last (TEAM)', 'AVG.' column

        Prefers NFBC if available, falls back to legacy CSV.
        """
        nfbc_file = self.data_dir / "adp_nfbc.tsv"
        legacy_file = self.data_dir / "adp.csv"

        adp_dict = {}

        if nfbc_file.exists():
            # NFBC TSV format: "Last, First" in Player column, ADP column
            with open(nfbc_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    name_raw = row.get('Player', '').strip()
                    adp_str = row.get('ADP', '').strip()
                    if not name_raw or not adp_str:
                        continue
                    # Convert "Last, First" to "First Last"
                    if ',' in name_raw:
                        parts = name_raw.split(',', 1)
                        name = f'{parts[1].strip()} {parts[0].strip()}'
                    else:
                        name = name_raw
                    try:
                        adp = float(adp_str)
                    except (ValueError, TypeError):
                        continue
                    normalized_name = self.normalize_player_name(name)
                    adp_dict[normalized_name] = adp
        elif legacy_file.exists():
            # Legacy CSV format: "First Last (TEAM)" in Player Name column
            with open(legacy_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    player_name = row.get('Player Name', '').strip()
                    if not player_name:
                        continue
                    name = player_name
                    if '(' in player_name and ')' in player_name:
                        parts = player_name.rsplit('(', 1)
                        name = parts[0].strip()
                    adp_str = row.get('AVG.', '').strip()
                    try:
                        adp = float(adp_str) if adp_str else None
                    except (ValueError, TypeError):
                        adp = None
                    if adp is not None:
                        normalized_name = self.normalize_player_name(name)
                        adp_dict[normalized_name] = adp
        else:
            return

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
        Get list of players with blended consensus projections.
        Averages across all available projection sources (Steamer, ATC, Depth Charts, etc.).
        Uses CBS data as base for player identity/availability.
        """
        master_dict = self.load_master_dict(player_type)
        players = []

        if player_type == "batters":
            stat_keys = [
                'projected_home_runs', 'projected_obp', 'projected_runs',
                'projected_rbi', 'projected_stolen_bases',
            ]
        else:
            stat_keys = [
                'projected_wins', 'projected_quality_starts', 'projected_strikeouts',
                'projected_era', 'projected_whip', 'projected_saves',
                'projected_holds', 'projected_innings_pitched',
            ]

        for normalized_name, player_data in master_dict.items():
            cbs_data = player_data.get('cbs_data', {})
            if not cbs_data:
                continue

            projections = player_data.get('projections', {})
            if not projections:
                continue

            # Blend stats across all available projection sources
            blended = {}
            for stat in stat_keys:
                values = []
                for source_data in projections.values():
                    val = source_data.get(stat)
                    if val is not None:
                        values.append(val)
                blended[stat] = sum(values) / len(values) if values else None

            # Get position/team from first available source
            position = cbs_data.get('position') or ''
            team = cbs_data.get('team') or ''
            age = cbs_data.get('age')
            if not position or not team:
                for source_data in projections.values():
                    if not position:
                        position = source_data.get('position') or ''
                    if not team:
                        team = source_data.get('team') or ''
                    if not age:
                        age = source_data.get('age')

            adp = player_data.get('adp')

            player = Player(
                player_id=cbs_data.get('player_id', normalized_name),
                name=cbs_data.get('name', player_data['name']),
                position=position,
                team=team,
                age=age,
                adp=adp,
                **blended,
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
                    'projected_innings_pitched': player.projected_innings_pitched,
                }
        
        self.save_master_dict(master_dict, player_type)
        return master_dict

