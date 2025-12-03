"""Service for loading player data from CSV files."""
import csv
import os
from typing import List, Dict
from pathlib import Path
from src.models.player import Player


class DataLoader:
    """Handles loading player data from files."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Default to project root/data
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.batters_dir = self.data_dir / "batters"
        self.pitchers_dir = self.data_dir / "pitchers"
        self.batters_dir.mkdir(parents=True, exist_ok=True)
        self.pitchers_dir.mkdir(parents=True, exist_ok=True)
    
    def load_players_from_csv(self, filename: str = None, file_type: str = "batters") -> List[Player]:
        """
        Load players from a CSV file.
        Supports both standard format and FanGraphs/Steamer format.
        
        Args:
            filename: Name of the file (if None, uses default based on file_type)
            file_type: "batters" or "pitchers" - determines which directory to look in
        """
        if filename is None:
            filename = "steamer-batters.csv" if file_type == "batters" else "steamer-pitchers.csv"
        
        # Determine which directory to use
        if file_type == "pitchers":
            filepath = self.pitchers_dir / filename
        else:
            filepath = self.batters_dir / filename
        
        if not filepath.exists():
            return []
        
        players = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Handle both lowercase and capitalized column names (FanGraphs uses capitals)
                    # Normalize column names to lowercase for easier matching
                    normalized_row = {k.lower().strip(): v for k, v in row.items()}
                    
                    # Get name (handle both 'name' and 'Name', or 'player' for CBS)
                    name = normalized_row.get('name', normalized_row.get('player', '')).strip()
                    if not name:
                        continue  # Skip rows without names
                    
                    # Parse CBS format: "Player Name (Batter) POS • TEAM" or "Player Name P • TEAM"
                    position = normalized_row.get('position', '').strip()
                    team = normalized_row.get('team', '').strip()
                    
                    # Parse CBS player format if present
                    if 'player' in normalized_row:
                        player_str = normalized_row.get('player', '')
                        # Format: "Shohei Ohtani (Batter) DH • LAD" or "Tarik Skubal P • DET"
                        if '•' in player_str:
                            parts = player_str.split('•')
                            if len(parts) == 2:
                                team = parts[1].strip()
                                # Extract position and name from first part
                                first_part = parts[0].strip()
                                
                                # Check for position after closing parenthesis: "(Batter) DH" or "(Batter) OF"
                                if ')' in first_part:
                                    # Has format like "Name (Batter) POS"
                                    paren_end = first_part.rfind(')')
                                    name = first_part[:first_part.find('(')].strip()
                                    # Position is after the closing parenthesis
                                    pos_part = first_part[paren_end + 1:].strip()
                                    if pos_part and not position:
                                        position = pos_part
                                else:
                                    # Format like "Tarik Skubal P" - position is last word
                                    name_parts = first_part.rsplit(' ', 1)
                                    if len(name_parts) == 2:
                                        # Check if last part looks like a position (1-3 chars, common positions)
                                        last_part = name_parts[1].strip()
                                        common_positions = ['P', 'SP', 'RP', 'C', '1B', '2B', '3B', 'SS', 'OF', 'DH', 'MI', 'CI', 'U']
                                        if last_part in common_positions or len(last_part) <= 3:
                                            name = name_parts[0].strip()
                                            if not position:
                                                position = last_part
                                        else:
                                            name = first_part.strip()
                                    else:
                                        name = first_part.strip()
                    
                    # Get team (handle both 'team' and 'Team')
                    if not team:
                        team = normalized_row.get('team', '').strip()
                    
                    # Create player_id from name
                    player_id = name.lower().replace(' ', '_').replace('.', '').replace("'", "")
                    
                    # Get age
                    age = self._safe_int(normalized_row.get('age'))
                    
                    # Batting stats (Bob Uecker League: HR, OBP, R, RBI, SB)
                    # Handle both 'hr' and 'HR', 'projected_home_runs', etc.
                    # Also handle CBS format: HR, OBP, R, RBI, SB
                    projected_home_runs = self._safe_float(
                        normalized_row.get('projected_home_runs') or 
                        normalized_row.get('hr')
                    )
                    projected_obp = self._safe_float(
                        normalized_row.get('projected_obp') or 
                        normalized_row.get('obp')
                    )
                    projected_runs = self._safe_float(
                        normalized_row.get('projected_runs') or 
                        normalized_row.get('r')
                    )
                    projected_rbi = self._safe_float(
                        normalized_row.get('projected_rbi') or 
                        normalized_row.get('rbi')
                    )
                    projected_stolen_bases = self._safe_float(
                        normalized_row.get('projected_stolen_bases') or 
                        normalized_row.get('sb')
                    )
                    
                    # Pitching stats (Bob Uecker League: ERA, K, SHOLDS, WHIP, WQS)
                    projected_wins = self._safe_float(
                        normalized_row.get('projected_wins') or 
                        normalized_row.get('w')
                    )
                    # Quality Starts - use GS as proxy if QS not available
                    projected_quality_starts = self._safe_float(
                        normalized_row.get('projected_quality_starts') or 
                        normalized_row.get('qs')
                    )
                    if projected_quality_starts is None:
                        # Use GS (games started) as rough proxy for QS
                        gs = self._safe_float(normalized_row.get('gs') or normalized_row.get('games_started') or normalized_row.get('app'))
                        if gs is not None:
                            # Rough estimate: ~60-70% of GS are QS
                            projected_quality_starts = gs * 0.65
                    
                    # Calculate total strikeouts from K/9 and IP if needed
                    projected_strikeouts = self._safe_float(
                        normalized_row.get('projected_strikeouts') or 
                        normalized_row.get('k') or 
                        normalized_row.get('so')
                    )
                    # If we have K/9 and IP, calculate total K
                    if projected_strikeouts is None:
                        k_per_9 = self._safe_float(normalized_row.get('k/9') or normalized_row.get('k9'))
                        ip = self._safe_float(normalized_row.get('ip') or normalized_row.get('inns') or normalized_row.get('innings_pitched'))
                        if k_per_9 is not None and ip is not None:
                            projected_strikeouts = (k_per_9 * ip) / 9.0
                    
                    projected_era = self._safe_float(
                        normalized_row.get('projected_era') or 
                        normalized_row.get('era')
                    )
                    
                    # Calculate WHIP from BB/9 and hits if available, or use direct WHIP
                    projected_whip = self._safe_float(
                        normalized_row.get('projected_whip') or 
                        normalized_row.get('whip')
                    )
                    # If WHIP not directly available, calculate from BB, H, and IP (CBS format)
                    if projected_whip is None:
                        bb = self._safe_float(normalized_row.get('bb'))
                        h = self._safe_float(normalized_row.get('h'))
                        ip = self._safe_float(normalized_row.get('ip') or normalized_row.get('inns') or normalized_row.get('innings_pitched'))
                        if bb is not None and h is not None and ip is not None and ip > 0:
                            projected_whip = (bb + h) / ip
                        else:
                            # Fallback: estimate from BB/9
                            bb_per_9 = self._safe_float(normalized_row.get('bb/9') or normalized_row.get('bb9'))
                            if bb_per_9 is not None:
                                projected_whip = (bb_per_9 + 8.5) / 9.0
                    
                    projected_saves = self._safe_float(
                        normalized_row.get('projected_saves') or 
                        normalized_row.get('sv') or
                        normalized_row.get('s')  # CBS uses 'S'
                    )
                    projected_holds = self._safe_float(
                        normalized_row.get('projected_holds') or 
                        normalized_row.get('hld') or 
                        normalized_row.get('holds') or
                        normalized_row.get('hd')  # CBS uses 'HD'
                    )
                    
                    # Auto-assign positions based on stats
                    if not position:
                        # Check if it's a pitcher (has pitching stats)
                        if projected_wins is not None or projected_era is not None or projected_saves is not None:
                            # If has saves, likely a RP; otherwise SP
                            if projected_saves and projected_saves > 0:
                                position = 'RP'
                            else:
                                position = 'SP'
                        # If it's a batter (has batting stats but no pitching stats)
                        elif projected_home_runs is not None or projected_runs is not None or projected_rbi is not None:
                            # Default to OF if we can't determine - user will need to update
                            # This is a placeholder - ideally positions should be in the CSV
                            position = 'OF'  # Most common position, user can update later
                    
                    player = Player(
                        player_id=player_id,
                        name=name,
                        position=position,  # May be empty if not in file
                        team=team,
                        age=age,
                        projected_home_runs=projected_home_runs,
                        projected_obp=projected_obp,
                        projected_runs=projected_runs,
                        projected_rbi=projected_rbi,
                        projected_stolen_bases=projected_stolen_bases,
                        projected_wins=projected_wins,
                        projected_quality_starts=projected_quality_starts,
                        projected_strikeouts=projected_strikeouts,
                        projected_era=projected_era,
                        projected_whip=projected_whip,
                        projected_saves=projected_saves,
                        projected_holds=projected_holds,
                    )
                    players.append(player)
                except Exception as e:
                    print(f"Error loading player from row: {e}")
                    print(f"Row data: {row}")
                    continue
        
        return players
    
    def save_players_to_csv(self, players: List[Player], filename: str = "projections.csv", file_type: str = "batters"):
        """Save players to a CSV file."""
        if file_type == "pitchers":
            filepath = self.pitchers_dir / filename
        else:
            filepath = self.batters_dir / filename
        
        if not players:
            return
        
        fieldnames = [
            'player_id', 'name', 'position', 'team', 'age',
            'projected_home_runs', 'projected_obp', 'projected_runs', 'projected_rbi',
            'projected_stolen_bases',
            'projected_wins', 'projected_quality_starts', 'projected_strikeouts', 
            'projected_era', 'projected_whip', 'projected_saves', 'projected_holds',
            'drafted', 'drafted_by_team', 'draft_round', 'draft_pick'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for player in players:
                writer.writerow(player.to_dict())
    
    @staticmethod
    def _safe_int(value) -> int:
        """Safely convert value to int."""
        if value is None or value == '':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _safe_float(value) -> float:
        """Safely convert value to float."""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

