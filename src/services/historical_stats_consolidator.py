"""Consolidates historical stats into unified structure - removes separate CBS/Savant keys."""
import json
from pathlib import Path
from typing import Dict, List


class HistoricalStatsConsolidator:
    """
    Consolidates historical stats structure.
    Merges CBS and Savant data into single 'stats' object.
    Removes separate 'cbs' key after merging.
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.master_dict_file = project_root / "data" / "sources" / "adp" / "players.json"
    
    def consolidate_historical_stats(self) -> Dict:
        """
        Consolidates all historical stats into unified structure.
        Returns consolidation report.
        """
        print("=" * 60)
        print("Consolidating Historical Stats Structure")
        print("=" * 60)
        
        # Load master dict
        print("\n1. Loading master player dictionary...")
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        
        players = master_data['players']
        print(f"   Loaded {len(players)} players")
        
        # Consolidate each player
        print("\n2. Consolidating historical stats...")
        consolidated_count = 0
        stats_merged_count = 0
        
        for player in players:
            if 'historical_stats' not in player:
                continue
            
            consolidated = self._consolidate_player_stats(player)
            if consolidated:
                consolidated_count += 1
                if consolidated.get('stats_merged'):
                    stats_merged_count += 1
        
        # Save updated master dict
        print("\n3. Saving consolidated master player dictionary...")
        with open(self.master_dict_file, 'w', encoding='utf-8') as f:
            json.dump({'players': players}, f, indent=2)
        
        print(f"\n✅ Consolidation complete!")
        print(f"   Players with historical stats: {consolidated_count}")
        print(f"   Players with merged CBS/Savant stats: {stats_merged_count}")
        
        return {
            'total_players': len(players),
            'players_with_historical_stats': consolidated_count,
            'players_with_merged_stats': stats_merged_count
        }
    
    def _consolidate_player_stats(self, player: Dict) -> Dict:
        """Consolidate historical stats for a single player."""
        if 'historical_stats' not in player:
            return None
        
        stats_merged = False
        
        for year, year_data in player['historical_stats'].items():
            # Check if we need to consolidate
            if 'cbs' in year_data:
                # Merge CBS stats into main stats if not already done
                cbs_data = year_data['cbs']
                cbs_stats = cbs_data.get('stats', {}) if isinstance(cbs_data, dict) else {}
                
                # Ensure 'stats' key exists
                if 'stats' not in year_data:
                    year_data['stats'] = {}
                
                # Merge CBS stats into main stats (if not already there)
                for field, value in cbs_stats.items():
                    if field not in year_data['stats']:
                        year_data['stats'][field] = value
                        stats_merged = True
                
                # Remove 'cbs' key after merging
                del year_data['cbs']
        
        return {'stats_merged': stats_merged} if stats_merged else {}
    
    def verify_consolidation(self) -> Dict:
        """Verify consolidation was successful."""
        print("\n" + "=" * 60)
        print("Verifying Consolidation")
        print("=" * 60)
        
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            master_data = json.load(f)
        
        players_with_cbs_key = 0
        players_with_unified_stats = 0
        total_years_with_stats = 0
        
        for player in master_data['players']:
            if 'historical_stats' not in player:
                continue
            
            for year, year_data in player['historical_stats'].items():
                total_years_with_stats += 1
                
                if 'cbs' in year_data:
                    players_with_cbs_key += 1
                
                if 'stats' in year_data:
                    players_with_unified_stats += 1
        
        print(f"\nTotal years with historical stats: {total_years_with_stats}")
        print(f"Years still with 'cbs' key: {players_with_cbs_key}")
        print(f"Years with unified 'stats' key: {players_with_unified_stats}")
        
        if players_with_cbs_key == 0:
            print("\n✅ Consolidation successful - no 'cbs' keys remaining!")
        else:
            print(f"\n⚠️  {players_with_cbs_key} years still have 'cbs' keys")
        
        return {
            'years_with_cbs_key': players_with_cbs_key,
            'years_with_unified_stats': players_with_unified_stats,
            'total_years': total_years_with_stats
        }



