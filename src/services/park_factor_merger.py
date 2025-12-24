"""Merges park factor data into master player dictionary."""
import csv
import json
from pathlib import Path
from typing import Dict


class ParkFactorMerger:
    """
    Merges park factor data into master player dictionary.
    Matches players to their team's park factors.
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        self.master_dict_file = project_root / "data" / "sources" / "adp" / "players.json"
        # Find the park factor file (use newest CSV in park_factors directory)
        park_factors_dir = project_root / "raw" / "park_factors"
        csv_files = list(park_factors_dir.glob("*.csv"))
        if csv_files:
            # Use the newest file
            self.park_factor_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        else:
            raise FileNotFoundError(f"No park factor CSV files found in {park_factors_dir}")
        
        # Team name mapping (NFBC/CBS team abbreviations to park factor team names)
        self.team_mapping = {
            'ARI': 'Diamondbacks', 'ARZ': 'Diamondbacks',
            'ATL': 'Braves',
            'BAL': 'Orioles',
            'BOS': 'Red Sox',
            'CHC': 'Cubs',
            'CWS': 'White Sox', 'CHW': 'White Sox',
            'CIN': 'Reds',
            'CLE': 'Guardians',
            'COL': 'Rockies',
            'DET': 'Tigers',
            'HOU': 'Astros',
            'KC': 'Royals', 'KCR': 'Royals',
            'LAA': 'Angels', 'LAA': 'Angels',
            'LAD': 'Dodgers',
            'MIA': 'Marlins',
            'MIL': 'Brewers', 'MLW': 'Brewers',
            'MIN': 'Twins',
            'NYM': 'Mets',
            'NYY': 'Yankees',
            'OAK': 'Athletics', 'ATH': 'Athletics',
            'PHI': 'Phillies',
            'PIT': 'Pirates',
            'SD': 'Padres', 'SDP': 'Padres',
            'SEA': 'Mariners',
            'SF': 'Giants', 'SFG': 'Giants',
            'STL': 'Cardinals',
            'TB': 'Rays', 'TBR': 'Rays',
            'TEX': 'Rangers',
            'TOR': 'Blue Jays',
            'WAS': 'Nationals', 'WSH': 'Nationals', 'WSN': 'Nationals'
        }
    
    def merge_park_factors(self) -> Dict:
        """
        Merges park factor data into master player dictionary.
        Returns merge report.
        """
        print("=" * 60)
        print("Merging Park Factor Data into Master Player Dictionary")
        print("=" * 60)
        
        # Load park factors
        print("\n1. Loading park factor data...")
        park_factors = self._load_park_factors()
        print(f"   Loaded park factors for {len(park_factors)} teams")
        
        # Load master dict
        print("\n2. Loading master player dictionary...")
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        players = master_data['players']
        print(f"   Loaded {len(players)} players from master dict")
        
        # Match and merge
        print("\n3. Matching players to park factors...")
        matched_count = 0
        unmatched_teams = set()
        
        for player in players:
            team = player.get('team', '')
            if not team:
                continue
            
            # Map team abbreviation to park factor team name
            park_team = self.team_mapping.get(team, team)
            
            # Find park factor for this team
            park_factor = None
            for pf_team, pf_data in park_factors.items():
                if pf_team.lower() == park_team.lower() or pf_team.lower() in park_team.lower() or park_team.lower() in pf_team.lower():
                    park_factor = pf_data
                    break
            
            if park_factor:
                # Merge park factor into player
                if 'park_factors' not in player:
                    player['park_factors'] = {}
                
                player['park_factors']['2025'] = park_factor
                matched_count += 1
            else:
                unmatched_teams.add(team)
        
        # Save updated master dict
        print("\n4. Saving updated master player dictionary...")
        with open(self.master_dict_file, 'w', encoding='utf-8') as f:
            json.dump({'players': players}, f, indent=2)
        
        # Report
        print(f"\n✅ Merge complete!")
        print(f"   Players matched to park factors: {matched_count}")
        if unmatched_teams:
            print(f"   Teams without park factors: {sorted(unmatched_teams)}")
        
        return {
            'matched_players': matched_count,
            'unmatched_teams': sorted(unmatched_teams) if unmatched_teams else []
        }
    
    def _load_park_factors(self) -> Dict[str, Dict]:
        """Load park factor data from CSV file."""
        park_factors = {}
        
        with open(self.park_factor_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                team = row.get('Team', '').strip()
                if not team:
                    continue
                
                # Extract park factor data
                park_data = {
                    'venue': row.get('Venue', '').strip(),
                    'year': row.get('Year', '').strip(),
                    'park_factor': self._safe_int(row.get('Park Factor')),
                    'woba_con': self._safe_int(row.get('wOBACon')),
                    'xwoba_con': self._safe_int(row.get('xwOBACon')),
                    'bacon': self._safe_int(row.get('BACON')),
                    'xbacon': self._safe_int(row.get('xBACON')),
                    'hard_hit': self._safe_int(row.get('HardHit')),
                    'runs': self._safe_int(row.get('R')),
                    'obp': self._safe_int(row.get('OBP')),
                    'hits': self._safe_int(row.get('H')),
                    'singles': self._safe_int(row.get('1B')),
                    'doubles': self._safe_int(row.get('2B')),
                    'triples': self._safe_int(row.get('3B')),
                    'home_runs': self._safe_int(row.get('HR')),
                    'walks': self._safe_int(row.get('BB')),
                    'strikeouts': self._safe_int(row.get('SO')),
                    'plate_appearances': self._safe_int(row.get('PA', '').replace(',', ''))
                }
                
                park_factors[team] = park_data
        
        return park_factors
    
    @staticmethod
    def _safe_int(value) -> int:
        """Safely convert value to int."""
        if not value or value == '' or value == '-':
            return None
        try:
            # Remove commas and convert
            clean_value = str(value).strip().replace(',', '')
            return int(clean_value)
        except (ValueError, TypeError):
            return None

