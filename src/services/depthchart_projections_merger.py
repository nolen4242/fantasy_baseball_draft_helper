"""Merges DepthChart projections into master player dictionary."""
import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple
from src.services.player_matcher import PlayerMatcher


class DepthChartProjectionsMerger:
    """
    Merges DepthChart projections into master player dictionary.
    Only includes players that exist in master dict (NFBC ADP is source of truth).
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        self.master_dict_file = project_root / "data" / "sources" / "adp" / "players.json"
        self.depthchart_batters_file = project_root / "raw" / "projections" / "fangraphs_depthchart_proj_2025.csv"
        self.depthchart_pitchers_file = project_root / "raw" / "projections" / "fangraphs_depthchart_pitchers_2025.csv"
        
        self.player_matcher = PlayerMatcher()
    
    def merge_depthchart_projections(self) -> Dict:
        """
        Merges DepthChart projections (batters and pitchers) into master player dictionary.
        Returns merge report.
        """
        print("=" * 60)
        print("Merging DepthChart Projections into Master Player Dictionary")
        print("=" * 60)
        
        # Load master dict
        print("\n1. Loading master player dictionary...")
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        master_players = {p['normalized_name']: p for p in master_data['players']}
        print(f"   Loaded {len(master_players)} players from master dict")
        
        # Load DepthChart projections (batters and pitchers)
        print("\n2. Loading DepthChart projections...")
        depthchart_batters = self._load_depthchart_projections(self.depthchart_batters_file, is_pitcher=False) if self.depthchart_batters_file.exists() else {}
        depthchart_pitchers = self._load_depthchart_projections(self.depthchart_pitchers_file, is_pitcher=True) if self.depthchart_pitchers_file.exists() else {}
        depthchart_players = {**depthchart_batters, **depthchart_pitchers}
        print(f"   Loaded {len(depthchart_batters)} batters and {len(depthchart_pitchers)} pitchers from DepthChart")
        
        # Match and merge
        print("\n3. Matching and merging DepthChart projections...")
        matched_count = 0
        unmatched_depthchart = []
        
        for depthchart_norm, depthchart_data in depthchart_players.items():
            # Try exact match first
            master_player = master_players.get(depthchart_norm)
            
            # If no exact match, try fuzzy matching
            if not master_player:
                master_player, matched_name = self._find_fuzzy_match(depthchart_norm, master_players)
                if master_player:
                    matched_count += 1
                else:
                    unmatched_depthchart.append(depthchart_data['name'])
                    continue
            
            # Merge projections into master player
            self._merge_projections(master_player, depthchart_data)
        
        # Save updated master dict
        print("\n4. Saving updated master player dictionary...")
        master_players_list = list(master_players.values())
        with open(self.master_dict_file, 'w', encoding='utf-8') as f:
            json.dump({'players': master_players_list}, f, indent=2)
        
        # Report
        print(f"\n✅ Merge complete!")
        print(f"   Matched DepthChart players: {len(depthchart_players) - len(unmatched_depthchart)}")
        print(f"   Unmatched DepthChart players: {len(unmatched_depthchart)}")
        
        if unmatched_depthchart:
            print(f"\n   Unmatched DepthChart players (not in master dict):")
            for name in unmatched_depthchart[:20]:
                print(f"   - {name}")
            if len(unmatched_depthchart) > 20:
                print(f"   ... and {len(unmatched_depthchart) - 20} more")
        
        return {
            'matched_players': len(depthchart_players) - len(unmatched_depthchart),
            'unmatched_depthchart': len(unmatched_depthchart)
        }
    
    def _load_depthchart_projections(self, filepath: Path, is_pitcher: bool = False) -> Dict[str, Dict]:
        """Load DepthChart projections from CSV file."""
        players = {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                name = row.get('Name', '').strip()
                if not name:
                    continue
                
                normalized_name = self.player_matcher.normalize_player_name(name)
                
                # Extract all projection fields
                projections = self._extract_projections(row, is_pitcher=is_pitcher)
                
                players[normalized_name] = {
                    'name': name,
                    'normalized_name': normalized_name,
                    'team': row.get('Team', '').strip(),
                    'projections': projections
                }
        
        return players
    
    def _extract_projections(self, row: Dict, is_pitcher: bool = False) -> Dict:
        """Extract projection fields from DepthChart row."""
        projections = {}
        
        if is_pitcher:
            # Pitcher stats
            # Counting stats
            counting_stats = {
                'W': 'wins',
                'L': 'losses',
                'SV': 'saves',
                'G': 'games',
                'GS': 'games_started',
                'IP': 'innings_pitched'
            }
            
            for depthchart_key, our_key in counting_stats.items():
                value = self._safe_float(row.get(depthchart_key))
                if value is not None:
                    projections[our_key] = value
            
            # Rate stats per 9 innings
            rate_stats = {
                'K/9': 'strikeouts_per_9',
                'BB/9': 'walks_per_9',
                'HR/9': 'home_runs_per_9'
            }
            
            for depthchart_key, our_key in rate_stats.items():
                value = self._safe_float(row.get(depthchart_key))
                if value is not None:
                    projections[our_key] = value
            
            # Calculate total strikeouts from K/9 and IP
            if 'strikeouts_per_9' in projections and 'innings_pitched' in projections:
                projections['strikeouts'] = (projections['strikeouts_per_9'] * projections['innings_pitched']) / 9.0
            
            # Calculate total walks from BB/9 and IP
            if 'walks_per_9' in projections and 'innings_pitched' in projections:
                projections['walks'] = (projections['walks_per_9'] * projections['innings_pitched']) / 9.0
            
            # ERA and FIP
            era = self._safe_float(row.get('ERA'))
            if era is not None:
                projections['era'] = era
            
            fip = self._safe_float(row.get('FIP'))
            if fip is not None:
                projections['fip'] = fip
            
            # Calculate WHIP from components: WHIP = (BB + H) / IP
            # We have walks from BB/9, but need to estimate hits
            if 'walks' in projections and 'innings_pitched' in projections:
                walks = projections['walks']
                ip = projections['innings_pitched']
                if ip and ip > 0:
                    # Estimate hits from league-average H/9 rate (~8.5-9.0 H/9)
                    # Use BABIP if available to refine estimate, otherwise use league average
                    league_avg_h_per_9 = 8.7  # Typical league average
                    if 'babip' in projections and projections['babip']:
                        # Adjust H/9 based on BABIP (higher BABIP = more hits)
                        babip = projections['babip']
                        # Normalize BABIP effect (league avg BABIP ~0.300)
                        babip_factor = babip / 0.300
                        estimated_h_per_9 = league_avg_h_per_9 * babip_factor
                    else:
                        estimated_h_per_9 = league_avg_h_per_9
                    
                    estimated_hits = (estimated_h_per_9 * ip) / 9.0
                    projections['whip'] = (walks + estimated_hits) / ip
            
            # Advanced stats
            advanced_stats = {
                'BABIP': 'babip',
                'LOB%': 'left_on_base_percentage',
                'GB%': 'ground_ball_percentage',
                'WAR': 'war'
            }
            
            for depthchart_key, our_key in advanced_stats.items():
                value_str = row.get(depthchart_key, '').strip()
                if value_str:
                    # Remove % sign if present
                    value_str = value_str.rstrip('%')
                    value = self._safe_float(value_str)
                    if value is not None:
                        projections[our_key] = value
            
            # Calculate quality starts (more realistic rates, capped at realistic max)
            if 'games_started' in projections:
                gs = projections['games_started']
                era = projections.get('era', 4.0)
                # More realistic QS rates based on actual data (elite pitchers cap at ~23 QS)
                if era < 3.00:
                    projections['quality_starts'] = min(gs * 0.65, 23)  # Elite: 65%, cap at 23
                elif era < 3.50:
                    projections['quality_starts'] = min(gs * 0.58, 22)  # Very good: 58%, cap at 22
                elif era < 4.00:
                    projections['quality_starts'] = min(gs * 0.50, 20)  # Good: 50%, cap at 20
                elif era < 4.50:
                    projections['quality_starts'] = min(gs * 0.45, 18)  # Average: 45%, cap at 18
                else:
                    projections['quality_starts'] = min(gs * 0.38, 16)  # Below average: 38%, cap at 16
                
                # CRITICAL: Cap QS based on IP (each QS requires at least 6 IP)
                # A pitcher with 50 IP can't have more than 50/6 = 8 QS
                if 'innings_pitched' in projections and projections['innings_pitched']:
                    max_qs_from_ip = projections['innings_pitched'] / 6.0
                    projections['quality_starts'] = min(projections['quality_starts'], max_qs_from_ip)
            
        else:
            # Batter stats
            # Standard counting stats
            counting_stats = {
                'G': 'games',
                'PA': 'plate_appearances',
                'HR': 'home_runs',
                'R': 'runs',
                'RBI': 'rbi',
                'SB': 'stolen_bases'
            }
            
            for depthchart_key, our_key in counting_stats.items():
                value = self._safe_float(row.get(depthchart_key))
                if value is not None:
                    projections[our_key] = value
            
            # Rate stats (remove % signs)
            rate_stats = {
                'BB%': 'walk_percentage',
                'K%': 'strikeout_percentage',
                'ISO': 'isolated_power',
                'BABIP': 'babip',
                'AVG': 'batting_average',
                'OBP': 'on_base_percentage',
                'SLG': 'slugging_percentage',
                'wOBA': 'woba'
            }
            
            for depthchart_key, our_key in rate_stats.items():
                value_str = row.get(depthchart_key, '').strip()
                if value_str:
                    # Remove % sign if present
                    value_str = value_str.rstrip('%')
                    value = self._safe_float(value_str)
                    if value is not None:
                        projections[our_key] = value
            
            # Advanced metrics
            advanced_stats = {
                'wRC+': 'wrc_plus',
                'BsR': 'baserunning_runs',
                'Off': 'offensive_runs',
                'Def': 'defensive_runs',
                'WAR': 'war'
            }
            
            for depthchart_key, our_key in advanced_stats.items():
                value = self._safe_float(row.get(depthchart_key))
                if value is not None:
                    projections[our_key] = value
        
        return projections
    
    def _find_fuzzy_match(self, normalized_name: str, master_players: Dict) -> Tuple[Dict, str]:
        """Find fuzzy match for DepthChart player in master dict."""
        best_match = None
        best_score = 0.0
        threshold = 0.85
        
        for master_norm, master_player in master_players.items():
            score = self.player_matcher.calculate_name_similarity(normalized_name, master_norm)
            if score >= threshold and score > best_score:
                best_score = score
                best_match = (master_player, master_norm)
        
        return best_match if best_match else (None, None)
    
    def _merge_projections(self, master_player: Dict, depthchart_data: Dict):
        """Merge DepthChart projections into master player."""
        # Ensure projections section exists
        if 'projections' not in master_player:
            master_player['projections'] = {}
        
        # Ensure 2025 projections exist
        if '2025' not in master_player['projections']:
            master_player['projections']['2025'] = {}
        
        # Add DepthChart projections for 2025
        master_player['projections']['2025']['depthchart'] = depthchart_data['projections']
    
    @staticmethod
    def _safe_float(value) -> float:
        """Safely convert value to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            # Remove any commas or other formatting
            clean_value = str(value).strip().replace(',', '')
            return float(clean_value)
        except (ValueError, TypeError):
            return None

