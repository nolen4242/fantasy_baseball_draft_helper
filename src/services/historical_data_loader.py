"""Load and process historical draft data and standings for ML training."""
import csv
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HistoricalPick:
    """Represents a pick in a historical draft."""
    year: int
    pick_number: int
    round: int
    team_name: str
    player_name: str
    position: str
    player_team: str  # MLB team
    is_pitcher: bool


@dataclass
class HistoricalStandings:
    """Represents final standings for a year."""
    year: int
    team_points: Dict[str, float]  # Team name -> total points
    category_totals: Dict[str, Dict[str, float]]  # Category -> Team -> Value
    category_points: Dict[str, Dict[str, float]]  # Category -> Team -> Points


class HistoricalDataLoader:
    """Loads historical draft and standings data."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "raw"
        self.data_dir = Path(data_dir)
        self.drafts_dir = self.data_dir / "drafts"
        self.standings_dir = self.data_dir / "historical_data"
    
    def load_historical_drafts(self, years: List[int] = None) -> Dict[int, List[HistoricalPick]]:
        """
        Load historical drafts from CSV files.
        
        Returns:
            Dict mapping year -> list of picks
        """
        if years is None:
            years = [2021, 2022, 2023, 2024, 2025]
        
        all_drafts = {}
        
        for year in years:
            draft_file = self.drafts_dir / f"cbs_{year}_season.csv"
            if not draft_file.exists():
                print(f"Warning: Draft file not found for year {year}: {draft_file}")
                continue
            
            picks = self._parse_draft_csv(draft_file, year)
            all_drafts[year] = picks
            print(f"Loaded {len(picks)} picks from {year} draft")
        
        return all_drafts
    
    def _parse_draft_csv(self, filepath: Path, year: int) -> List[HistoricalPick]:
        """Parse a draft CSV file."""
        picks = []
        current_round = 0
        pick_counter = 0
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                
                # Check if this is a round header
                if row[0] and row[0].strip().startswith("Round"):
                    match = re.search(r'Round\s+(\d+)', row[0])
                    if match:
                        current_round = int(match.group(1))
                    continue
                
                # Skip header rows
                if row[0] == "Pick" or row[0].strip() == "":
                    continue
                
                # Parse pick row: Pick,Team,Player,Elig,Elapsed Time
                if len(row) < 3:
                    continue
                
                try:
                    pick_number_in_round = int(row[0].strip())
                    team_name = row[1].strip()
                    player_str = row[2].strip()
                    
                    # Parse player string: "Player Name Position | MLB Team" or "*Player Name Position | MLB Team"
                    is_pitcher = player_str.startswith("*")
                    if is_pitcher:
                        player_str = player_str[1:].strip()
                    
                    # Split by "|" to get name+position and team
                    parts = player_str.split("|")
                    if len(parts) != 2:
                        continue
                    
                    name_pos = parts[0].strip()
                    player_team = parts[1].strip()
                    
                    # Extract position from name_pos (usually at the end)
                    # Format: "Name Position" or "Name Pos1,Pos2 Position"
                    name_pos_parts = name_pos.rsplit(" ", 1)
                    if len(name_pos_parts) == 2:
                        player_name = name_pos_parts[0].strip()
                        position = name_pos_parts[1].strip()
                        # Remove multiple positions, keep primary (first one)
                        if "," in position:
                            position = position.split(",")[0].strip()
                    else:
                        continue
                    
                    # Calculate absolute pick number
                    # Assuming 13 teams (adjust if needed)
                    pick_counter += 1
                    
                    pick = HistoricalPick(
                        year=year,
                        pick_number=pick_counter,
                        round=current_round,
                        team_name=team_name,
                        player_name=player_name,
                        position=position,
                        player_team=player_team,
                        is_pitcher=is_pitcher or position in ['P', 'SP', 'RP']
                    )
                    
                    picks.append(pick)
                except (ValueError, IndexError) as e:
                    print(f"Error parsing row in {filepath}: {row} - {e}")
                    continue
        
        return picks
    
    def load_historical_standings(self, years: List[int] = None) -> Dict[int, HistoricalStandings]:
        """
        Load historical standings from CSV files.
        
        Returns:
            Dict mapping year -> standings
        """
        if years is None:
            years = [2021, 2022, 2023, 2024, 2025]
        
        all_standings = {}
        
        for year in years:
            standings_file = self.standings_dir / f"cbs_{year}_league_results.csv"
            if not standings_file.exists():
                print(f"Warning: Standings file not found for year {year}: {standings_file}")
                continue
            
            standings = self._parse_standings_csv(standings_file, year)
            all_standings[year] = standings
            print(f"Loaded standings for {year}: {len(standings.team_points)} teams")
        
        return all_standings
    
    def _parse_standings_csv(self, filepath: Path, year: int) -> HistoricalStandings:
        """Parse a standings CSV file."""
        team_points = {}
        category_totals = {}  # category -> team -> value
        category_points = {}  # category -> team -> points
        
        # Categories in order
        batting_categories = ['HR', 'OBP', 'R', 'RBI', 'SB']
        pitching_categories = ['ERA', 'K', 'S', 'WHIP', 'WQS']  # Note: 'S' is saves, 'SHOLDS' in current system
        
        current_category = None
        reading_category = False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                
                # Look for overall standings
                if len(row) >= 4 and row[0].strip().isdigit():
                    try:
                        rank = int(row[0].strip())
                        team_name = row[1].strip()
                        batting_pts = float(row[2]) if row[2] else 0.0
                        pitching_pts = float(row[3]) if row[3] else 0.0
                        total_pts = batting_pts + pitching_pts
                        team_points[team_name] = total_pts
                    except (ValueError, IndexError):
                        pass
                
                # Look for category breakdowns
                if len(row) >= 2:
                    # Check if this is a category header
                    if row[0].strip() == "Team" and row[1].strip() in batting_categories + pitching_categories:
                        current_category = row[1].strip()
                        reading_category = True
                        if current_category not in category_totals:
                            category_totals[current_category] = {}
                            category_points[current_category] = {}
                        continue
                
                # Read category data
                if reading_category and current_category and len(row) >= 3:
                    try:
                        team_name = row[0].strip()
                        category_value_str = row[1].strip()
                        points_str = row[2].strip()
                        
                        # Parse category value (could be float or int)
                        if category_value_str:
                            category_value = float(category_value_str)
                        else:
                            continue
                        
                        # Parse points
                        points = float(points_str) if points_str else 0.0
                        
                        category_totals[current_category][team_name] = category_value
                        category_points[current_category][team_name] = points
                    except (ValueError, IndexError):
                        pass
        
        # Convert 'S' (Saves) to 'SHOLDS' for consistency with current system
        if 'S' in category_totals:
            category_totals['SHOLDS'] = category_totals.pop('S')
            category_points['SHOLDS'] = category_points.pop('S')
        
        return HistoricalStandings(
            year=year,
            team_points=team_points,
            category_totals=category_totals,
            category_points=category_points
        )



