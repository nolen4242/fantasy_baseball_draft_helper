"""CBS historical data processor - adds historical stats to existing 2025 players only."""
import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple, Set
from src.services.player_matcher import PlayerMatcher


class CBSHistoricalProcessor:
    """
    Processes historical CBS data (2021-2024) and adds stats to existing 2025 players.
    Only updates players who exist in 2025 data - does not create new players.
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.raw_dir = project_root / "raw" / "historical_data"
        self.historical_stats_dir = project_root / "data" / "sources" / "historical_stats"
        self.position_eligibility_dir = project_root / "data" / "sources" / "position_eligibility"
        
        self.player_matcher = PlayerMatcher()
        
        # Years to process (2021-2024)
        self.historical_years = [2021, 2022, 2023, 2024]
    
    def process_historical_data(self) -> Dict:
        """
        Main processing function.
        Loads 2025 players, then adds historical stats from 2021-2024.
        """
        print("=" * 60)
        print("Processing CBS Historical Data (2021-2024)")
        print("=" * 60)
        
        # Step 1: Load existing 2025 players (from position_eligibility)
        print("\n1. Loading 2025 players...")
        players_2025 = self._load_2025_players()
        print(f"   Found {len(players_2025)} players from 2025 data")
        
        # Step 2: Create lookup by normalized name
        players_by_normalized = {p['normalized_name']: p for p in players_2025}
        
        # Step 3: Process each historical year
        stats_added = 0
        players_with_history = 0
        
        for year in self.historical_years:
            print(f"\n2. Processing {year} data...")
            year_stats = self._load_historical_year(year, players_by_normalized)
            
            # Add stats to 2025 players
            for normalized_name, stats in year_stats.items():
                if normalized_name in players_by_normalized:
                    player = players_by_normalized[normalized_name]
                    if 'historical_stats' not in player:
                        player['historical_stats'] = {}
                    
                    year_key = str(year)
                    if year_key not in player['historical_stats']:
                        player['historical_stats'][year_key] = {}
                    
                    # Store stats by source (allows multiple sources per year)
                    player['historical_stats'][year_key]['cbs'] = {
                        'stats': stats['stats'],
                        'position': stats.get('position'),
                        'team': stats.get('team')
                    }
                    
                    stats_added += 1
                    if len(player.get('historical_stats', {})) > 0:
                        players_with_history += 1
        
        # Count unique players with historical data
        unique_players_with_history = len([p for p in players_by_normalized.values() if p.get('historical_stats')])
        
        print(f"\n   Stats entries added: {stats_added}")
        print(f"   Unique players with historical data: {unique_players_with_history}")
        
        # Step 4: Update historical_stats file
        print("\n3. Updating historical_stats file...")
        self._update_historical_stats_file(players_2025)
        
        unique_players_with_history = len([p for p in players_by_normalized.values() if p.get('historical_stats')])
        
        print(f"\n✅ Historical data processing complete!")
        print(f"   Updated {unique_players_with_history} players with historical stats")
        
        return {
            'players_updated': unique_players_with_history,
            'stats_entries_added': stats_added,
            'years_processed': self.historical_years
        }
    
    def _load_2025_players(self) -> List[Dict]:
        """Load existing 2025 players from position_eligibility."""
        position_file = self.position_eligibility_dir / "players.json"
        
        if not position_file.exists():
            raise FileNotFoundError("2025 players not found. Run CBS processor first.")
        
        with open(position_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['players']
    
    def _load_historical_year(self, year: int, players_2025_lookup: Dict) -> Dict[str, Dict]:
        """
        Load historical data for a specific year.
        Returns dict mapping normalized_name to stats (only for players in 2025).
        """
        year_stats = {}
        
        # Find all CSV files for this year
        year_files = list(self.raw_dir.glob(f"cbs_*_{year}_*.csv"))
        
        if not year_files:
            print(f"   No files found for {year}")
            return year_stats
        
        print(f"   Found {len(year_files)} files for {year}")
        
        # Process each file
        for filepath in year_files:
            # Determine position from filename
            position = self._extract_position_from_filename(filepath.name)
            if not position:
                continue
            
            # Load players from this file
            players_from_file = self._load_historical_file(filepath, position, year)
            
            # Match to 2025 players
            for player_data in players_from_file:
                normalized_name = player_data['normalized_name']
                
                # Only add if player exists in 2025
                if normalized_name in players_2025_lookup:
                    # If we already have stats for this year from another file, merge positions
                    if normalized_name in year_stats:
                        # Stats should be the same, but we can verify
                        existing_stats = year_stats[normalized_name]
                        if existing_stats.get('stats') != player_data.get('stats'):
                            # Stats differ - might be different player or data issue
                            print(f"   ⚠️  Stats mismatch for {player_data['name']} in {year}")
                    else:
                        year_stats[normalized_name] = {
                            'stats': player_data['stats'],
                            'position': player_data.get('position'),
                            'team': player_data.get('team')
                        }
        
        return year_stats
    
    def _extract_position_from_filename(self, filename: str) -> str:
        """Extract position from filename like 'cbs_catchers_2024_stats.csv'."""
        # Remove extension and split
        parts = filename.replace('.csv', '').split('_')
        
        # Look for position indicators
        if 'catcher' in filename.lower() or 'c_' in filename.lower():
            return 'C'
        elif '1b' in filename.lower():
            return '1B'
        elif '2b' in filename.lower():
            return '2B'
        elif '3b' in filename.lower():
            return '3B'
        elif 'ss' in filename.lower():
            return 'SS'
        elif 'of' in filename.lower():
            return 'OF'
        elif 'pitcher' in filename.lower() or 'p_' in filename.lower():
            return 'P'
        elif 'u' in filename.lower() and len(parts) > 2:
            return 'U'
        
        return None
    
    def _load_historical_file(self, filepath: Path, position: str, year: int) -> List[Dict]:
        """Load players from a historical CSV file."""
        players = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # Skip first line (title row)
                first_line = f.readline()
                
                # Read the actual header row
                header_line = f.readline().strip()
                if not header_line:
                    return []
                
                # Parse header
                header_cols = [col.strip() for col in header_line.split(',')]
                
                # Create reader
                reader = csv.DictReader(f, fieldnames=header_cols)
                
                for row in reader:
                    if not row:
                        continue
                    
                    # Skip header rows
                    player_str = row.get('Player', '').strip() if row.get('Player') else ''
                    if not player_str or player_str.startswith('All ') or player_str == 'Player' or player_str == '':
                        continue
                    
                    # Parse player string
                    name, positions_list, team = self._parse_player_string(player_str)
                    
                    if not name:
                        continue
                    
                    # Normalize name
                    normalized_name = self.player_matcher.normalize_player_name(name)
                    
                    # Determine if hitter or pitcher
                    is_pitcher = position == 'P' or 'P' in positions_list or 'SP' in positions_list or 'RP' in positions_list
                    
                    # Extract stats
                    stats = {}
                    if is_pitcher:
                        stats = {
                            'era': self._safe_float(row.get('ERA')),
                            'strikeouts': self._safe_float(row.get('K')),
                            'whip': self._safe_float(row.get('WHIP')),
                            'saves': self._safe_float(row.get('SHOLDS')),  # Note: SHOLDS in CBS
                            'wins': self._safe_float(row.get('WQS')),  # Note: WQS in CBS
                        }
                    else:
                        stats = {
                            'home_runs': self._safe_float(row.get('HR')),
                            'obp': self._safe_float(row.get('OBP')),
                            'runs': self._safe_float(row.get('R')),
                            'rbi': self._safe_float(row.get('RBI')),
                            'stolen_bases': self._safe_float(row.get('SB')),
                        }
                    
                    players.append({
                        'name': name,
                        'normalized_name': normalized_name,
                        'position': position,
                        'team': team,
                        'stats': stats,
                        'year': year
                    })
        except Exception as e:
            print(f"   ⚠️  Error loading {filepath.name}: {e}")
        
        return players
    
    def _parse_player_string(self, player_str: str) -> Tuple[str, List[str], str]:
        """Parse player string like 'Aaron Judge OF | NYY' or 'Ben Rice C,1B | NYY'."""
        # Split by "|" to separate name/position from team
        if '|' in player_str:
            parts = player_str.split('|')
            name_part = parts[0].strip()
            team = parts[1].strip() if len(parts) > 1 else None
        else:
            name_part = player_str.strip()
            team = None
        
        # Extract positions
        positions_list = []
        valid_positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P', 'U']
        
        name_clean = name_part
        for pos in valid_positions:
            if f',{pos}' in name_clean or f'{pos},' in name_clean:
                positions_list.append(pos)
            elif name_clean.endswith(f' {pos}') or f' {pos} ' in name_clean:
                if pos not in positions_list:
                    positions_list.append(pos)
        
        # Remove positions from name
        name = name_part
        for pos in valid_positions:
            name = name.replace(f',{pos}', '').replace(f'{pos},', '')
            if name.endswith(f' {pos}'):
                name = name[:-len(f' {pos}')].strip()
            elif f' {pos} ' in name:
                name = name.replace(f' {pos} ', ' ')
        
        # Clean up name
        name = name.strip().rstrip(',').strip()
        
        if not positions_list:
            positions_list = ['U']
        
        return name, positions_list, team
    
    def _update_historical_stats_file(self, players: List[Dict]):
        """Update the historical_stats file with historical data."""
        output_file = self.historical_stats_dir / "players.json"
        
        # Convert to output format
        stats_data = []
        for player in players:
            if player.get('historical_stats'):
                stats_data.append({
                    'unified_id': player['unified_id'],
                    'name': player['name'],
                    'normalized_name': player['normalized_name'],
                    'position': player.get('position'),
                    'team': player.get('team'),
                    'historical_stats': player['historical_stats'],
                    'source': 'cbs'
                })
        
        # Save
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'players': stats_data
            }, f, indent=2)
        
        # Update metadata
        from datetime import datetime
        metadata = {
            'source': 'cbs',
            'load_date': datetime.now().isoformat(),
            'player_count': len(stats_data),
            'description': 'Historical stats data from CBS (2021-2024)',
            'years_included': [2021, 2022, 2023, 2024, 2025]
        }
        
        metadata_file = self.historical_stats_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Updated {len(stats_data)} players with historical stats")
    
    def _safe_float(self, value) -> float:
        """Safely convert to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

