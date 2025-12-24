"""Merges Baseball Savant data into master player dictionary."""
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple
from src.services.player_matcher import PlayerMatcher


class SavantMerger:
    """
    Merges Savant Statcast data into master player dictionary.
    Handles field conflicts and alerts on mismatches.
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        self.master_dict_file = project_root / "data" / "sources" / "adp" / "players.json"
        self.savant_file = project_root / "data" / "sources" / "savant" / "players.json"
        
        self.player_matcher = PlayerMatcher()
        
        # Fields that might overlap between CBS and Savant
        self.overlapping_fields = {
            'home_runs', 'runs', 'rbi', 'stolen_bases', 'caught_stealing',
            'hits', 'doubles', 'triples', 'singles',
            'at_bats', 'plate_appearances', 'strikeouts', 'walks',
            'batting_average', 'slugging_percentage', 'on_base_percentage',
            'ops', 'babip', 'strikeout_percentage', 'walk_percentage'
        }
    
    def merge_savant_into_master(self) -> Dict:
        """
        Merges Savant data into master player dictionary.
        Returns merge report with conflicts.
        """
        print("=" * 60)
        print("Merging Savant Data into Master Player Dictionary")
        print("=" * 60)
        
        # Load master dict
        print("\n1. Loading master player dictionary...")
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        master_players = {p['normalized_name']: p for p in master_data['players']}
        print(f"   Loaded {len(master_players)} players from master dict")
        
        # Load Savant data
        print("\n2. Loading Savant data...")
        with open(self.savant_file, 'r', encoding='utf-8') as f:
            savant_data = json.load(f)
        savant_players = {p['normalized_name']: p for p in savant_data['players']}
        print(f"   Loaded {len(savant_players)} players from Savant")
        
        # Match and merge
        print("\n3. Matching and merging Savant data...")
        matched_count = 0
        unmatched_savant = []
        conflicts = []
        
        for savant_norm, savant_player in savant_players.items():
            # Try exact match first
            master_player = master_players.get(savant_norm)
            
            # If no exact match, try fuzzy matching
            if not master_player:
                master_player, matched_name = self._find_fuzzy_match(savant_norm, master_players)
                if master_player:
                    matched_count += 1
                else:
                    unmatched_savant.append(savant_player['name'])
                    continue
            
            # Merge Savant data into master player
            conflicts.extend(self._merge_savant_stats(master_player, savant_player))
        
        # Save updated master dict
        print("\n4. Saving updated master player dictionary...")
        master_players_list = list(master_players.values())
        with open(self.master_dict_file, 'w', encoding='utf-8') as f:
            json.dump({'players': master_players_list}, f, indent=2)
        
        # Report
        print(f"\n✅ Merge complete!")
        print(f"   Matched Savant players: {len(savant_players) - len(unmatched_savant)}")
        print(f"   Unmatched Savant players: {len(unmatched_savant)}")
        print(f"   Field conflicts found: {len(conflicts)}")
        
        if unmatched_savant:
            print(f"\n⚠️  Unmatched Savant players (not in master dict):")
            for name in unmatched_savant[:20]:
                print(f"   - {name}")
            if len(unmatched_savant) > 20:
                print(f"   ... and {len(unmatched_savant) - 20} more")
        
        if conflicts:
            print(f"\n⚠️  Field conflicts detected (CBS vs Savant):")
            for conflict in conflicts[:20]:
                print(f"   {conflict}")
            if len(conflicts) > 20:
                print(f"   ... and {len(conflicts) - 20} more conflicts")
        
        return {
            'matched_players': len(savant_players) - len(unmatched_savant),
            'unmatched_savant': len(unmatched_savant),
            'conflicts': len(conflicts),
            'conflict_details': conflicts
        }
    
    def _find_fuzzy_match(self, normalized_name: str, master_players: Dict) -> Tuple[Dict, str]:
        """Find fuzzy match for Savant player in master dict."""
        best_match = None
        best_score = 0.0
        threshold = 0.85
        
        for master_norm, master_player in master_players.items():
            score = self.player_matcher.calculate_name_similarity(normalized_name, master_norm)
            if score >= threshold and score > best_score:
                best_score = score
                best_match = (master_player, master_norm)
        
        return best_match if best_match else (None, None)
    
    def _merge_savant_stats(self, master_player: Dict, savant_player: Dict) -> List[str]:
        """
        Merge Savant stats into master player's historical_stats.
        Filters out irrelevant stats (pitcher stats for batters, batter stats for pitchers).
        Only Shohei Ohtani gets both batting and pitching stats.
        Returns list of conflict messages.
        """
        conflicts = []
        
        # Ensure historical_stats exists
        if 'historical_stats' not in master_player:
            master_player['historical_stats'] = {}
        
        # Determine player type
        player_name = master_player.get('name', '').lower()
        primary_position = master_player.get('primary_position', '')
        is_ohtani = 'ohtani' in player_name and 'shohei' in player_name
        is_pitcher = primary_position == 'P'
        is_batter = primary_position != 'P' and primary_position != ''
        
        # Define stat categories
        pitcher_stats = {'era', 'whip', 'saves', 'wins', 'quality_starts', 'holds'}
        batter_stats = {'home_runs', 'runs', 'rbi', 'stolen_bases', 'obp', 'batting_average', 
                       'slugging_percentage', 'on_base_percentage', 'ops', 'hits', 'doubles', 
                       'triples', 'singles', 'at_bats', 'plate_appearances', 'walks', 'strikeouts'}
        
        # Process each year in Savant data
        for year, savant_year_data in savant_player.get('historical_stats', {}).items():
            if year not in master_player['historical_stats']:
                master_player['historical_stats'][year] = {}
            
            # Get existing CBS data for this year (if any)
            cbs_data = master_player['historical_stats'][year].get('cbs', {})
            cbs_stats = cbs_data.get('stats', {}) if isinstance(cbs_data, dict) else {}
            
            # Get Savant stats and Statcast
            savant_stats = savant_year_data.get('stats', {})
            savant_statcast = savant_year_data.get('statcast', {})
            
            # Filter CBS stats based on player type
            filtered_cbs_stats = {}
            if cbs_stats:
                for field, value in cbs_stats.items():
                    # Ohtani gets everything
                    if is_ohtani:
                        filtered_cbs_stats[field] = value
                    # Pitchers only get pitcher stats
                    elif is_pitcher:
                        if field in pitcher_stats or 'strikeout' in field.lower():
                            filtered_cbs_stats[field] = value
                    # Batters only get batter stats
                    elif is_batter:
                        if field in batter_stats:
                            filtered_cbs_stats[field] = value
                    # Unknown position - keep everything for now
                    else:
                        filtered_cbs_stats[field] = value
            
            # Merge stats - check for conflicts
            merged_stats = {}
            
            # Start with filtered CBS stats
            if filtered_cbs_stats:
                merged_stats.update(filtered_cbs_stats)
            
            # Add/check Savant stats (also filter based on player type)
            for field, savant_value in savant_stats.items():
                # Filter Savant stats too
                should_include = False
                if is_ohtani:
                    should_include = True
                elif is_pitcher:
                    should_include = (field in pitcher_stats or 'strikeout' in field.lower())
                elif is_batter:
                    should_include = (field in batter_stats)
                else:
                    should_include = True
                
                if not should_include:
                    continue
                
                if field in merged_stats:
                    # Conflict detected
                    cbs_value = merged_stats[field]
                    if self._values_differ(cbs_value, savant_value):
                        # Prefer Savant data when there's a difference
                        # (Savant is more comprehensive and accurate for historical stats)
                        merged_stats[field] = savant_value  # Use Savant value
                        
                        # Report conflict for user awareness
                        conflict_msg = (
                            f"{master_player['name']} ({year}): {field} - "
                            f"CBS={cbs_value}, Savant={savant_value} (using Savant)"
                        )
                        conflicts.append(conflict_msg)
                    # If values match, keep existing value
                else:
                    # New field from Savant, add it
                    merged_stats[field] = savant_value
            
            # Store merged data
            master_player['historical_stats'][year]['stats'] = merged_stats
            master_player['historical_stats'][year]['statcast'] = savant_statcast
        
        return conflicts
    
    def _values_differ(self, val1, val2, tolerance: float = 0.01) -> bool:
        """Check if two values differ significantly."""
        if val1 is None or val2 is None:
            return val1 != val2
        
        try:
            # For numeric values, use tolerance
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                return abs(val1 - val2) > tolerance
            # For strings, exact match
            return str(val1) != str(val2)
        except (TypeError, ValueError):
            return str(val1) != str(val2)
    
    def _remove_parenthetical_text(self, name: str) -> str:
        """Remove parenthetical text from name for better matching."""
        import re
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'\s+(dh|ut|p|sp|rp|c|1b|2b|3b|ss|of)\s*$', '', name, flags=re.IGNORECASE)
        return name.strip()

