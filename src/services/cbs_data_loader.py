"""CBS data loader with duplicate handling and position eligibility."""
import csv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from src.models.player import Player
from src.services.player_matcher import PlayerMatcher


class CBSDataLoader:
    """
    Loads CBS data from position-specific CSV files.
    Handles duplicates (players with multiple position eligibility).
    """
    
    def __init__(self, raw_data_dir: str = None):
        if raw_data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            raw_data_dir = project_root / "raw"
        self.raw_data_dir = Path(raw_data_dir)
        self.player_matcher = PlayerMatcher()
        
        # Position file mapping
        self.position_files = {
            'C': 'cbs_catchers_2025_stats.csv',
            '1B': 'cbs_1b_2025_stats.csv',
            '2B': 'cbs_2b_2025_stats.csv',
            '3B': 'cbs_3b_2025_stats.csv',
            'SS': 'cbs_ss_2025_stats.csv',
            'OF': 'cbs_of_2025_stats.csv',
            'P': 'cbs_pitchers_2025_stats.csv',
        }
    
    def load_all_cbs_players(self) -> List[Player]:
        """
        Load all CBS players from position-specific files.
        Handles duplicates (same player in multiple files).
        
        Returns:
            List of Player objects with position eligibility
        """
        all_players_raw = []
        
        # Load players from each position file
        for position, filename in self.position_files.items():
            filepath = self.raw_data_dir / filename
            if not filepath.exists():
                print(f"Warning: {filename} not found, skipping {position}")
                continue
            
            players_from_file = self._load_position_file(filepath, position)
            all_players_raw.extend(players_from_file)
            print(f"Loaded {len(players_from_file)} players from {position} file")
        
        print(f"\nTotal players loaded (before deduplication): {len(all_players_raw)}")
        
        # Convert to dict format for matcher
        players_dict = []
        for player in all_players_raw:
            players_dict.append({
                'player_id': player.player_id,
                'name': player.name,
                'position': player.position,
                'position_eligibility': getattr(player, 'position_eligibility', [player.position]),
                'source': 'cbs',
                'player_obj': player
            })
        
        # Merge duplicates using player matcher
        merged_dicts = self.player_matcher.merge_duplicate_players(players_dict, source='cbs')
        
        # Convert back to Player objects
        merged_players = []
        for player_dict in merged_dicts:
            player_obj = player_dict.get('player_obj')
            if player_obj:
                # Update position eligibility
                if 'position_eligibility' in player_dict:
                    player_obj.position_eligibility = player_dict['position_eligibility']
                # Update primary position
                if 'position' in player_dict:
                    player_obj.position = player_dict['position']
                merged_players.append(player_obj)
        
        print(f"Total players after deduplication: {len(merged_players)}")
        print(f"Deduplicated {len(all_players_raw) - len(merged_players)} duplicate entries")
        
        return merged_players
    
    def _load_position_file(self, filepath: Path, position: str) -> List[Player]:
        """
        Load players from a single position file.
        
        Args:
            filepath: Path to CSV file
            position: Position identifier (C, 1B, 2B, etc.)
        
        Returns:
            List of Player objects
        """
        players = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip first line (title row like "All Outfielders 2025  Season MLB Scoring Categories")
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
                
                # Parse player name and team from "Name Position | Team" format
                player_str = row.get('Player', '').strip()
                if not player_str:
                    continue
                
                # Parse: "Aaron Judge OF | NYY" or "Ben Rice C,1B | NYY" -> name, positions, team
                name, positions_list, team = self._parse_player_string(player_str)
                
                if not name:
                    continue
                
                # Use positions from string, or fall back to file position
                if positions_list:
                    primary_position = positions_list[0]
                    position_eligibility = positions_list
                else:
                    primary_position = position
                    position_eligibility = [position]
                
                # Check if player is already drafted
                avail = row.get('Avail', '').strip()
                is_drafted = avail and avail not in ['', 'Available', 'Avail', 'W ']
                drafted_by = avail if is_drafted else None
                
                # Create player ID from normalized name
                normalized_name = self.player_matcher.normalize_player_name(name)
                player_id = f"cbs_{normalized_name.replace(' ', '_')}"
                
                # Determine if hitter or pitcher
                is_pitcher = primary_position == 'P' or 'P' in position_eligibility or 'SP' in position_eligibility or 'RP' in position_eligibility
                
                # Create Player object
                if is_pitcher:
                    player = Player(
                        player_id=player_id,
                        name=name,
                        position=primary_position,
                        team=team or '',
                        # Pitching stats
                        projected_era=self._safe_float(row.get('ERA')),
                        projected_strikeouts=self._safe_float(row.get('K')),
                        projected_whip=self._safe_float(row.get('WHIP')),
                        projected_saves=self._safe_float(row.get('SHOLDS')),  # Note: SHOLDS in CBS
                        projected_wins=self._safe_float(row.get('WQS')),  # Note: WQS in CBS
                        # Draft status
                        drafted=is_drafted,
                        drafted_by_team=drafted_by,
                    )
                else:
                    player = Player(
                        player_id=player_id,
                        name=name,
                        position=primary_position,
                        team=team or '',
                        # Batting stats
                        projected_home_runs=self._safe_float(row.get('HR')),
                        projected_obp=self._safe_float(row.get('OBP')),
                        projected_runs=self._safe_float(row.get('R')),
                        projected_rbi=self._safe_float(row.get('RBI')),
                        projected_stolen_bases=self._safe_float(row.get('SB')),
                        # Draft status
                        drafted=is_drafted,
                        drafted_by_team=drafted_by,
                    )
                
                # Set position eligibility (will be merged later if duplicate)
                player.position_eligibility = position_eligibility
                
                players.append(player)
        
        return players
    
    def _parse_player_string(self, player_str: str) -> Tuple[str, List[str], Optional[str]]:
        """
        Parse player string like "Aaron Judge OF | NYY" or "Ben Rice C,1B | NYY" into name, positions, and team.
        
        Returns:
            Tuple of (name, positions_list, team)
        """
        # Split by "|" to separate name/position from team
        if '|' in player_str:
            parts = player_str.split('|')
            name_part = parts[0].strip()
            team = parts[1].strip() if len(parts) > 1 else None
        else:
            name_part = player_str.strip()
            team = None
        
        # Extract positions (can be multiple: "C,1B" or single: "OF")
        positions_list = []
        valid_positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P']
        
        # Look for comma-separated positions (e.g., "C,1B")
        # Pattern: name ends with " Position1,Position2" or " Position"
        name_clean = name_part
        
        # Check for comma-separated positions at the end
        # Example: "Ben Rice C,1B" -> positions = ["C", "1B"]
        for pos in valid_positions:
            # Check for ",Position" pattern (comma before position)
            if f',{pos}' in name_clean:
                positions_list.append(pos)
            # Check for "Position," pattern (comma after position)
            elif f'{pos},' in name_clean:
                positions_list.append(pos)
            # Check for " Position " or " Position" at end (space-separated)
            elif name_clean.endswith(f' {pos}') or f' {pos} ' in name_clean:
                if pos not in positions_list:
                    positions_list.append(pos)
        
        # Remove positions from name
        name = name_clean
        for pos in valid_positions:
            # Remove position patterns
            name = name.replace(f',{pos}', '').replace(f'{pos},', '')
            # Remove space-separated positions (at end or middle)
            if name.endswith(f' {pos}'):
                name = name[:-len(f' {pos}')].strip()
            elif f' {pos} ' in name:
                name = name.replace(f' {pos} ', ' ')
        
        # Clean up name (remove extra spaces, commas, trailing punctuation)
        name = name.strip().rstrip(',').strip()
        
        # If no positions found, try to find single position at the end
        if not positions_list:
            for pos in valid_positions:
                if name_clean.endswith(f' {pos}'):
                    positions_list.append(pos)
                    name = name_clean[:-len(f' {pos}')].strip()
                    break
        
        # Ensure we have at least one position
        if not positions_list:
            positions_list = ['U']  # Default to Utility if no position found
        
        return name, positions_list, team
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

