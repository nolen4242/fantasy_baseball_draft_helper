"""CBS data processor - loads from raw/historical_data and outputs to data/sources/"""
import csv
import json
import uuid
from pathlib import Path
from typing import List, Dict, Tuple, Set
from src.services.player_matcher import PlayerMatcher
from src.services.data_cleaner import DataCleaner


class CBSProcessor:
    """
    Processes CBS data from raw/historical_data/ and outputs to data/sources/
    Handles:
    1. Name + unique identifier creation
    2. Position eligibility (merging duplicates)
    3. Historical stats (avoiding duplicates)
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.raw_dir = project_root / "raw" / "historical_data"
        self.position_eligibility_dir = project_root / "data" / "sources" / "position_eligibility"
        self.historical_stats_dir = project_root / "data" / "sources" / "historical_stats"
        
        # Ensure output directories exist
        self.position_eligibility_dir.mkdir(parents=True, exist_ok=True)
        self.historical_stats_dir.mkdir(parents=True, exist_ok=True)
        
        self.player_matcher = PlayerMatcher()
        self.data_cleaner = DataCleaner()
        
        # Position file mapping
        self.position_files = {
            'C': 'cbs_catchers_2025_stats.csv',
            '1B': 'cbs_1b_2025_stats.csv',
            '2B': 'cbs_2b_2025_stats.csv',
            '3B': 'cbs_3b_2025_stats.csv',
            'SS': 'cbs_ss_2025_stats.csv',
            'OF': 'cbs_of_2025_stats.csv',
            'U': 'cbs_u_2025_stats.csv',
            'P': 'cbs_pitchers_2025_stats.csv',
        }
    
    def process_cbs_data(self) -> Dict:
        """
        Main processing function.
        Returns processing report with mismatches and statistics.
        """
        print("=" * 60)
        print("Processing CBS Data")
        print("=" * 60)
        
        # Step 1: Load all players from position files
        all_players_raw = []
        for position, filename in self.position_files.items():
            filepath = self.raw_dir / filename
            if not filepath.exists():
                print(f"Warning: {filename} not found, skipping {position}")
                continue
            
            players_from_file = self._load_position_file(filepath, position)
            all_players_raw.extend(players_from_file)
            print(f"Loaded {len(players_from_file)} players from {position} file")
        
        print(f"\nTotal players loaded (before deduplication): {len(all_players_raw)}")
        
        # Step 2: Merge duplicates (same player in multiple position files)
        merged_players = self._merge_duplicate_players(all_players_raw)
        
        print(f"Total players after deduplication: {len(merged_players)}")
        print(f"Deduplicated {len(all_players_raw) - len(merged_players)} duplicate entries")
        
        # Step 3: Separate position data from stats data
        position_data = []
        stats_data = []
        
        for player in merged_players:
            # Position eligibility data
            position_data.append({
                'unified_id': player['unified_id'],
                'name': player['name'],
                'normalized_name': player['normalized_name'],
                'position': player['primary_position'],
                'position_eligibility': player['position_eligibility'],
                'team': player.get('team'),
                'source': 'cbs'
            })
            
            # Historical stats data (only if stats exist)
            if player.get('stats'):
                stats_data.append({
                    'unified_id': player['unified_id'],
                    'name': player['name'],
                    'normalized_name': player['normalized_name'],
                    'position': player['primary_position'],
                    'team': player.get('team'),
                    'stats': player['stats'],
                    'source': 'cbs',
                    'year': 2025  # Current season
                })
        
        # Step 4: Save to sources
        self._save_position_eligibility(position_data)
        self._save_historical_stats(stats_data)
        
        # Step 5: Generate report
        # Collect mismatches from merge process
        mismatches = []
        for normalized_name, group in self._player_groups_for_report.items():
            if len(group) > 1:
                names = [p['name'] for p in group]
                if len(set(names)) > 1:
                    mismatches.append({
                        'normalized_name': normalized_name,
                        'names': list(set(names)),
                        'confidence': 'needs_review',
                        'reason': 'Different name variations matched to same normalized name'
                    })
        
        report = {
            'total_players': len(merged_players),
            'position_eligibility_count': len(position_data),
            'historical_stats_count': len(stats_data),
            'duplicates_merged': len(all_players_raw) - len(merged_players),
            'mismatches': mismatches
        }
        
        print(f"\n✅ Processing complete!")
        print(f"   Position eligibility: {len(position_data)} players")
        print(f"   Historical stats: {len(stats_data)} players")
        
        return report
    
    def _load_position_file(self, filepath: Path, position: str) -> List[Dict]:
        """Load players from a single position file."""
        players = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip first line (title row)
            first_line = f.readline()
            
            # Read the actual header row
            header_line = f.readline().strip()
            if not header_line:
                return []
            
            # Parse header to get column names
            header_cols = [col.strip() for col in header_line.split(',')]
            
            # Create reader with proper headers
            reader = csv.DictReader(f, fieldnames=header_cols)
            
            for row in reader:
                if not row:
                    continue
                
                # Skip header rows or empty rows
                player_str = row.get('Player', '').strip() if row.get('Player') else ''
                if not player_str or player_str.startswith('All ') or player_str == 'Player' or player_str == '':
                    continue
                
                # Parse player string
                name, positions_list, team = self._parse_player_string(player_str)
                
                if not name:
                    continue
                
                # Normalize name for matching
                normalized_name = self.player_matcher.normalize_player_name(name)
                
                # Create unique identifier (UUID will be assigned during merge)
                # For now, use normalized name as temporary key
                unified_id = None  # Will be set during merge
                
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
                
                # Use positions from string, or fall back to file position
                if positions_list:
                    primary_position = positions_list[0]
                    position_eligibility = positions_list
                else:
                    primary_position = position
                    position_eligibility = [position]
                
                players.append({
                    'unified_id': None,  # Will be assigned during merge
                    'name': name,
                    'normalized_name': normalized_name,
                    'primary_position': primary_position,
                    'position_eligibility': position_eligibility,
                    'team': team,
                    'stats': stats,
                    'is_pitcher': is_pitcher,
                    'source_file': filepath.name
                })
        
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
        
        # Check for comma-separated positions
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
        
        # If no positions found, try to find single position at the end
        if not positions_list:
            for pos in valid_positions:
                if name_part.endswith(f' {pos}'):
                    positions_list.append(pos)
                    name = name_part[:-len(f' {pos}')].strip()
                    break
        
        if not positions_list:
            positions_list = ['U']
        
        return name, positions_list, team
    
    def _merge_duplicate_players(self, players: List[Dict]) -> List[Dict]:
        """
        Merge duplicate players (same player in multiple position files).
        Combines position eligibility and stats (avoiding duplicates).
        """
        # Group by normalized name
        player_groups: Dict[str, List[Dict]] = {}
        
        for player in players:
            normalized_name = player['normalized_name']
            
            if normalized_name not in player_groups:
                player_groups[normalized_name] = []
            player_groups[normalized_name].append(player)
        
        # Store for report
        self._player_groups_for_report = player_groups
        
        # Merge players with same normalized name
        merged_players = []
        mismatches = []
        
        for normalized_name, group in player_groups.items():
            if len(group) == 1:
                # No duplicates, assign UUID and add
                player = group[0].copy()
                player['unified_id'] = str(uuid.uuid4())
                merged_players.append(player)
            else:
                # Merge duplicates
                merged = self._merge_player_group(group, normalized_name)
                merged_players.append(merged)
                
                # Check for potential mismatches (different names with same normalized name)
                names = [p['name'] for p in group]
                if len(set(names)) > 1:
                    mismatches.append({
                        'normalized_name': normalized_name,
                        'names': names,
                        'confidence': 'needs_review',
                        'reason': 'Different name variations matched to same normalized name'
                    })
        
        if mismatches:
            print(f"\n⚠️  Found {len(mismatches)} potential name mismatches:")
            for mismatch in mismatches[:10]:  # Show first 10
                print(f"   {mismatch['normalized_name']}: {mismatch['names']}")
            if len(mismatches) > 10:
                print(f"   ... and {len(mismatches) - 10} more")
        
        return merged_players
    
    def _merge_player_group(self, players: List[Dict], normalized_name: str) -> Dict:
        """Merge a group of duplicate players into one."""
        if not players:
            return {}
        
        # Generate UUID for this player
        unified_id = str(uuid.uuid4())
        
        # Start with first player as base
        merged = players[0].copy()
        merged['unified_id'] = unified_id
        
        # Collect all positions
        positions = set(merged['position_eligibility'])
        for player in players[1:]:
            positions.update(player['position_eligibility'])
        
        # Update position eligibility
        merged['position_eligibility'] = sorted(list(positions))
        
        # Set primary position (prefer non-flexible positions)
        primary_positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P']
        for pos in primary_positions:
            if pos in positions:
                merged['primary_position'] = pos
                break
        else:
            merged['primary_position'] = sorted(list(positions))[0] if positions else 'U'
        
        # Merge stats (take first non-null value, avoid duplicates)
        # Stats should be the same across position files, so just use first
        if not merged.get('stats'):
            for player in players[1:]:
                if player.get('stats'):
                    merged['stats'] = player['stats']
                    break
        
        # Use most complete name (longest)
        names = [p['name'] for p in players]
        merged['name'] = max(names, key=len)
        
        return merged
    
    def _save_position_eligibility(self, position_data: List[Dict]):
        """Save position eligibility data to sources."""
        output_file = self.position_eligibility_dir / "players.json"
        metadata_file = self.position_eligibility_dir / "metadata.json"
        
        # Save players
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'players': position_data
            }, f, indent=2)
        
        # Save metadata
        from datetime import datetime
        metadata = {
            'source': 'cbs',
            'load_date': datetime.now().isoformat(),
            'player_count': len(position_data),
            'description': 'Position eligibility data from CBS'
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Saved position eligibility: {len(position_data)} players → {output_file}")
    
    def _save_historical_stats(self, stats_data: List[Dict]):
        """Save historical stats data to sources."""
        output_file = self.historical_stats_dir / "players.json"
        metadata_file = self.historical_stats_dir / "metadata.json"
        
        # Save players
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'players': stats_data
            }, f, indent=2)
        
        # Save metadata
        from datetime import datetime
        metadata = {
            'source': 'cbs',
            'load_date': datetime.now().isoformat(),
            'player_count': len(stats_data),
            'description': 'Historical stats data from CBS'
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Saved historical stats: {len(stats_data)} players → {output_file}")
    
    def _safe_float(self, value) -> float:
        """Safely convert to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

