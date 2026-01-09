"""Baseball Savant data processor - loads Statcast data and stores in intermediate format."""
import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from src.services.player_matcher import PlayerMatcher


class SavantProcessor:
    """
    Processes Baseball Savant Statcast data from raw CSV files.
    Stores in intermediate format, then merges into master player dict.
    """
    
    def __init__(self, raw_data_dir: Path = None, output_data_dir: Path = None):
        if raw_data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            raw_data_dir = project_root / "raw" / "historical_data"
        self.raw_data_dir = Path(raw_data_dir)
        
        if output_data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            output_data_dir = project_root / "data" / "sources" / "savant"
        self.output_data_dir = Path(output_data_dir)
        self.output_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.players_output = self.output_data_dir / "players.json"
        self.metadata_output = self.output_data_dir / "metadata.json"
        
        self.player_matcher = PlayerMatcher()
        self.savant_years = [2021, 2022, 2023, 2024, 2025]
    
    def process_savant_data(self) -> Dict:
        """
        Loads all Savant data files and processes them.
        Returns processing report.
        """
        print("=" * 60)
        print("Processing Baseball Savant Data")
        print("=" * 60)
        
        all_players: Dict[str, Dict] = {}  # Key: normalized_name, Value: player_data
        
        for year in self.savant_years:
            print(f"\nProcessing {year} data...")
            year_file = self.raw_data_dir / f"savant_{year}_stats.csv"
            
            if not year_file.exists():
                print(f"  Warning: {year_file} not found, skipping")
                continue
            
            year_players = self._load_savant_year(year_file, year)
            print(f"  Loaded {len(year_players)} players from {year}")
            
            # Merge into all_players
            for normalized_name, player_data in year_players.items():
                if normalized_name not in all_players:
                    all_players[normalized_name] = {
                        'unified_id': None,  # Will be set during merge
                        'name': player_data['name'],
                        'normalized_name': normalized_name,
                        'savant_player_id': player_data.get('player_id'),
                        'historical_stats': {}
                    }
                
                # Add year's stats
                all_players[normalized_name]['historical_stats'][str(year)] = {
                    'stats': player_data['stats'],
                    'statcast': player_data['statcast']
                }
        
        # Save intermediate file
        print(f"\nSaving intermediate Savant data...")
        players_list = list(all_players.values())
        self._save_json(self.players_output, {'players': players_list})
        
        # Save metadata
        from datetime import datetime
        metadata = {
            'source': 'baseball_savant',
            'load_date': datetime.now().isoformat(),
            'player_count': len(players_list),
            'years_processed': self.savant_years,
            'description': 'Baseball Savant Statcast data - intermediate format'
        }
        self._save_json(self.metadata_output, metadata)
        
        print(f"✅ Saved Savant data: {len(players_list)} players")
        print(f"   Output: {self.players_output}")
        
        return {
            'total_players': len(players_list),
            'years_processed': self.savant_years
        }
    
    def _load_savant_year(self, filepath: Path, year: int) -> Dict[str, Dict]:
        """Load a single year's Savant data."""
        players = {}
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Parse name (format: "Last, First")
                name_str = row.get('last_name, first_name', '').strip()
                if not name_str:
                    continue
                
                # Convert "Last, First" to "First Last"
                first_last_name = self._convert_savant_name_to_first_last(name_str)
                normalized_name = self.player_matcher.normalize_player_name(first_last_name)
                
                # Extract all stats
                stats = self._extract_standard_stats(row)
                statcast = self._extract_statcast_metrics(row)
                
                # Store player data
                players[normalized_name] = {
                    'name': first_last_name,
                    'normalized_name': normalized_name,
                    'player_id': row.get('player_id', '').strip(),
                    'year': year,
                    'stats': stats,
                    'statcast': statcast
                }
        
        return players
    
    def _convert_savant_name_to_first_last(self, savant_name: str) -> str:
        """Convert Savant name format "Last, First" to "First Last"."""
        if ',' in savant_name:
            parts = savant_name.split(',')
            if len(parts) == 2:
                last = parts[0].strip()
                first = parts[1].strip()
                return f"{first} {last}"
        # If no comma, assume it's already "First Last"
        return savant_name.strip()
    
    def _extract_standard_stats(self, row: Dict) -> Dict:
        """Extract standard batting stats from Savant row."""
        stats = {}
        
        # Standard counting stats (may overlap with CBS)
        standard_fields = {
            'ab': 'at_bats',
            'pa': 'plate_appearances',
            'hit': 'hits',
            'single': 'singles',
            'double': 'doubles',
            'triple': 'triples',
            'home_run': 'home_runs',
            'strikeout': 'strikeouts',
            'walk': 'walks',
            'b_rbi': 'rbi',
            'r_total_stolen_base': 'stolen_bases',
            'r_total_caught_stealing': 'caught_stealing',
            'r_run': 'runs',
            'b_intent_walk': 'intentional_walks'
        }
        
        for savant_key, our_key in standard_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                stats[our_key] = value
        
        # Rate stats
        rate_fields = {
            'batting_avg': 'batting_average',
            'slg_percent': 'slugging_percentage',
            'on_base_percent': 'on_base_percentage',
            'on_base_plus_slg': 'ops',
            'isolated_power': 'isolated_power',
            'babip': 'babip',
            'k_percent': 'strikeout_percentage',
            'bb_percent': 'walk_percentage'
        }
        
        for savant_key, our_key in rate_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                stats[our_key] = value
        
        return stats
    
    def _extract_statcast_metrics(self, row: Dict) -> Dict:
        """Extract Statcast-specific metrics from Savant row."""
        statcast = {}
        
        # Expected stats
        expected_fields = {
            'xba': 'expected_batting_average',
            'xslg': 'expected_slugging',
            'xwoba': 'expected_woba',
            'xobp': 'expected_obp'
        }
        
        for savant_key, our_key in expected_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                statcast[our_key] = value
        
        # Contact quality metrics
        contact_fields = {
            'exit_velocity_avg': 'exit_velocity_avg',
            'launch_angle_avg': 'launch_angle_avg',
            'sweet_spot_percent': 'sweet_spot_percentage',
            'barrel_batted_rate': 'barrel_rate',
            'hard_hit_percent': 'hard_hit_percentage'
        }
        
        for savant_key, our_key in contact_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                statcast[our_key] = value
        
        # Speed metrics
        speed_fields = {
            'avg_best_speed': 'avg_best_speed',
            'avg_hyper_speed': 'avg_hyper_speed',
            'sprint_speed': 'sprint_speed'
        }
        
        for savant_key, our_key in speed_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                statcast[our_key] = value
        
        # Plate discipline
        discipline_fields = {
            'whiff_percent': 'whiff_percentage',
            'swing_percent': 'swing_percentage'
        }
        
        for savant_key, our_key in discipline_fields.items():
            value = self._safe_float(row.get(savant_key))
            if value is not None:
                statcast[our_key] = value
        
        # Get any remaining fields that might be Statcast-specific
        all_statcast_keys = [
            'xba', 'xslg', 'xwoba', 'xobp',
            'exit_velocity_avg', 'launch_angle_avg', 'sweet_spot_percent',
            'barrel_batted_rate', 'hard_hit_percent',
            'avg_best_speed', 'avg_hyper_speed', 'sprint_speed',
            'whiff_percent', 'swing_percent'
        ]
        
        # Add any other fields that look Statcast-related
        for key, value in row.items():
            if key not in all_statcast_keys and value:
                # Check if it's a Statcast metric (numeric, not already captured)
                if any(x in key.lower() for x in ['x', 'velocity', 'angle', 'barrel', 'hard', 'speed', 'whiff', 'swing']):
                    clean_value = self._safe_float(value)
                    if clean_value is not None:
                        statcast[key] = clean_value
        
        return statcast
    
    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert value to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            # Remove quotes and convert
            clean_value = str(value).strip().strip('"')
            return float(clean_value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _save_json(filepath: Path, data: Dict):
        """Save data to a JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)



