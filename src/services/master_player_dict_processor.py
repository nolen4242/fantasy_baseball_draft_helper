"""Master player dict processor - creates master player dictionary from NFBC ADP + CBS data."""
import csv
import json
import uuid
from pathlib import Path
from typing import List, Dict, Tuple, Set
from src.services.player_matcher import PlayerMatcher


class MasterPlayerDictProcessor:
    """
    Creates master player dictionary using NFBC ADP as source of truth.
    - NFBC ADP players are included (even if not in CBS)
    - CBS players not in NFBC ADP are excluded
    - CBS data is merged into NFBC ADP entries
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.raw_dir = project_root / "raw" / "historical_data"
        self.sources_dir = project_root / "data" / "sources"
        self.output_dir = project_root / "data" / "sources" / "adp"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.player_matcher = PlayerMatcher()
    
    def create_master_player_dict(self) -> Dict:
        """
        Main processing function.
        Creates master player dict from NFBC ADP + CBS data.
        """
        print("=" * 60)
        print("Creating Master Player Dictionary")
        print("=" * 60)
        
        # Step 1: Load NFBC ADP (source of truth)
        print("\n1. Loading NFBC ADP data...")
        nfbc_players = self._load_nfbc_adp()
        print(f"   Loaded {len(nfbc_players)} players from NFBC ADP")
        
        # Step 2: Load CBS data
        print("\n2. Loading CBS data...")
        cbs_position_data = self._load_cbs_position_data()
        cbs_stats_data = self._load_cbs_stats_data()
        print(f"   Loaded {len(cbs_position_data)} players from CBS position data")
        print(f"   Loaded {len(cbs_stats_data)} players from CBS stats data")
        
        # Step 3: Match and merge
        print("\n3. Matching and merging data...")
        master_players, unmatched_nfbc, unmatched_cbs = self._match_and_merge(
            nfbc_players, cbs_position_data, cbs_stats_data
        )
        
        # Step 4: Alert on unmatched NFBC players
        if unmatched_nfbc:
            print(f"\n⚠️  ALERT: {len(unmatched_nfbc)} NFBC ADP players NOT found in CBS data:")
            for player_name in list(unmatched_nfbc)[:20]:  # Show first 20
                print(f"   - {player_name}")
            if len(unmatched_nfbc) > 20:
                print(f"   ... and {len(unmatched_nfbc) - 20} more")
            print("\n   These players will be included with ADP only (no CBS data)")
        
        # Step 5: Report unmatched CBS players (excluded)
        if unmatched_cbs:
            print(f"\n   Excluded {len(unmatched_cbs)} CBS players not in NFBC ADP")
        
        # Step 6: Check for team mismatches
        team_mismatches = self._check_team_mismatches(master_players)
        if team_mismatches:
            print(f"\n⚠️  Found {len(team_mismatches)} team mismatches between NFBC and CBS:")
            for player_name, nfbc_team, cbs_team in list(team_mismatches)[:10]:
                print(f"   - {player_name}: NFBC={nfbc_team}, CBS={cbs_team}")
            if len(team_mismatches) > 10:
                print(f"   ... and {len(team_mismatches) - 10} more")
        
        # Step 7: Save master player dict
        print("\n4. Saving master player dictionary...")
        self._save_master_player_dict(master_players)
        
        print(f"\n✅ Master player dictionary created!")
        print(f"   Total players: {len(master_players)}")
        print(f"   Players with CBS data: {len(master_players) - len(unmatched_nfbc)}")
        print(f"   Players with ADP only: {len(unmatched_nfbc)}")
        
        return {
            'total_players': len(master_players),
            'players_with_cbs_data': len(master_players) - len(unmatched_nfbc),
            'players_adp_only': len(unmatched_nfbc),
            'excluded_cbs_players': len(unmatched_cbs),
            'team_mismatches': len(team_mismatches) if team_mismatches else 0
        }
    
    def _load_nfbc_adp(self) -> List[Dict]:
        """Load NFBC ADP data from TSV file."""
        adp_file = self.raw_dir / "nfbc_adp_2026.tsv"
        
        if not adp_file.exists():
            raise FileNotFoundError(f"NFBC ADP file not found: {adp_file}")
        
        players = []
        
        with open(adp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:
                # Parse player name (NFBC format: "Last, First")
                player_name = row.get('Player', '').strip()
                if not player_name:
                    continue
                
                # Convert "Last, First" to "First Last"
                first_last_name = self._convert_nfbc_name_to_first_last(player_name)
                normalized_name = self.player_matcher.normalize_player_name(first_last_name)
                
                # Parse positions
                positions_str = row.get('Position(s)', '').strip()
                positions = [p.strip() for p in positions_str.split(',') if p.strip()]
                
                # Get primary position (first one)
                primary_position = positions[0] if positions else 'U'
                
                players.append({
                    'nfbc_player_id': row.get('Player ID', '').strip(),
                    'name': first_last_name,  # "First Last" format
                    'normalized_name': normalized_name,
                    'team_nfbc': row.get('Team', '').strip(),
                    'position_eligibility': positions,
                    'primary_position': primary_position,
                    'adp': self._safe_float(row.get('ADP')),
                    'min_pick': self._safe_int(row.get('Min Pick')),
                    'max_pick': self._safe_int(row.get('Max Pick')),
                    'rank': self._safe_int(row.get('Rank'))
                })
        
        return players
    
    def _convert_nfbc_name_to_first_last(self, nfbc_name: str) -> str:
        """Convert NFBC name format "Last, First" to "First Last"."""
        if ',' in nfbc_name:
            parts = nfbc_name.split(',')
            if len(parts) == 2:
                last = parts[0].strip()
                first = parts[1].strip()
                return f"{first} {last}"
        # If no comma, assume it's already "First Last"
        return nfbc_name.strip()
    
    def _load_cbs_position_data(self) -> Dict[str, Dict]:
        """Load CBS position eligibility data."""
        position_file = self.sources_dir / "position_eligibility" / "players.json"
        
        if not position_file.exists():
            print("   Warning: CBS position data not found")
            return {}
        
        with open(position_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create lookup by normalized name
        position_lookup = {}
        for player in data.get('players', []):
            normalized_name = player.get('normalized_name')
            if normalized_name:
                position_lookup[normalized_name] = player
        
        return position_lookup
    
    def _load_cbs_stats_data(self) -> Dict[str, Dict]:
        """Load CBS historical stats data."""
        stats_file = self.sources_dir / "historical_stats" / "players.json"
        
        if not stats_file.exists():
            print("   Warning: CBS stats data not found")
            return {}
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create lookup by normalized name
        stats_lookup = {}
        for player in data.get('players', []):
            normalized_name = player.get('normalized_name')
            if normalized_name:
                stats_lookup[normalized_name] = player
        
        return stats_lookup
    
    def _match_and_merge(
        self,
        nfbc_players: List[Dict],
        cbs_position_data: Dict[str, Dict],
        cbs_stats_data: Dict[str, Dict]
    ) -> Tuple[List[Dict], Set[str], Set[str]]:
        """Match NFBC players with CBS data and merge."""
        master_players = []
        unmatched_nfbc = set()
        matched_cbs_players = set()
        
        # Create list of CBS normalized names for fuzzy matching
        cbs_normalized_names = list(cbs_position_data.keys()) + list(cbs_stats_data.keys())
        cbs_normalized_names = list(set(cbs_normalized_names))
        
        for nfbc_player in nfbc_players:
            normalized_name = nfbc_player['normalized_name']
            
            # Try exact match first
            cbs_position = cbs_position_data.get(normalized_name)
            cbs_stats = cbs_stats_data.get(normalized_name)
            
            # If no exact match, try fuzzy matching
            if not cbs_position and not cbs_stats:
                best_match = self._find_fuzzy_match(normalized_name, cbs_normalized_names, cbs_position_data, cbs_stats_data)
                if best_match:
                    cbs_position, cbs_stats, matched_name = best_match
                    matched_cbs_players.add(matched_name)
                else:
                    # NFBC player not in CBS - include with ADP only
                    unmatched_nfbc.add(nfbc_player['name'])
            else:
                # Found exact CBS match - merge data
                matched_cbs_players.add(normalized_name)
            
            master_player = self._create_master_player(nfbc_player, cbs_position, cbs_stats)
            master_players.append(master_player)
        
        # Find CBS players not in NFBC ADP (excluded)
        all_cbs_players = set(cbs_position_data.keys()) | set(cbs_stats_data.keys())
        unmatched_cbs = all_cbs_players - matched_cbs_players
        
        return master_players, unmatched_nfbc, unmatched_cbs
    
    def _find_fuzzy_match(
        self,
        normalized_name: str,
        cbs_normalized_names: List[str],
        cbs_position_data: Dict[str, Dict],
        cbs_stats_data: Dict[str, Dict]
    ) -> Tuple[Dict, Dict, str]:
        """Find fuzzy match for normalized name."""
        best_match = None
        best_score = 0.0
        threshold = 0.85  # High confidence threshold (lowered to catch cases like Ohtani)
        
        # Clean normalized name (remove parenthetical text for better matching)
        clean_nfbc_name = self._remove_parenthetical_text(normalized_name)
        
        for cbs_norm in cbs_normalized_names:
            # Clean CBS name too
            clean_cbs_name = self._remove_parenthetical_text(cbs_norm)
            
            # Try matching both cleaned and original
            score1 = self.player_matcher.calculate_name_similarity(clean_nfbc_name, clean_cbs_name)
            score2 = self.player_matcher.calculate_name_similarity(normalized_name, cbs_norm)
            score = max(score1, score2)
            
            if score >= threshold and score > best_score:
                best_score = score
                best_match = (
                    cbs_position_data.get(cbs_norm),
                    cbs_stats_data.get(cbs_norm),
                    cbs_norm
                )
        
        return best_match
    
    def _remove_parenthetical_text(self, name: str) -> str:
        """Remove parenthetical text like '(Batter)', '(Pitcher)', 'DH' from name."""
        import re
        # Remove text in parentheses
        name = re.sub(r'\([^)]*\)', '', name)
        # Remove common suffixes like "DH", "UT", etc. that might be at the end
        name = re.sub(r'\s+(dh|ut|p|sp|rp|c|1b|2b|3b|ss|of)\s*$', '', name, flags=re.IGNORECASE)
        return name.strip()
    
    def _create_master_player(
        self,
        nfbc_player: Dict,
        cbs_position: Dict,
        cbs_stats: Dict
    ) -> Dict:
        """Create master player entry from NFBC + CBS data."""
        # Use CBS player ID if available, otherwise generate UUID
        if cbs_position and cbs_position.get('unified_id'):
            unified_id = cbs_position['unified_id']
        else:
            unified_id = str(uuid.uuid4())
        
        # Use CBS position eligibility (as specified)
        if cbs_position and cbs_position.get('position_eligibility'):
            position_eligibility = cbs_position['position_eligibility']
            primary_position = cbs_position.get('position') or position_eligibility[0] if position_eligibility else nfbc_player['primary_position']
        else:
            position_eligibility = nfbc_player['position_eligibility']
            primary_position = nfbc_player['primary_position']
        
        # Team: use CBS if available, otherwise NFBC
        team = None
        if cbs_position and cbs_position.get('team'):
            team = cbs_position['team']
        elif cbs_stats and cbs_stats.get('team'):
            team = cbs_stats['team']
        else:
            team = nfbc_player.get('team_nfbc')
        
        # Check for team mismatch
        team_mismatch = None
        if cbs_position and cbs_position.get('team') and nfbc_player.get('team_nfbc'):
            if cbs_position['team'] != nfbc_player['team_nfbc']:
                team_mismatch = {
                    'nfbc': nfbc_player['team_nfbc'],
                    'cbs': cbs_position['team']
                }
        
        # Build master player
        master_player = {
            'unified_id': unified_id,
            'name': nfbc_player['name'],
            'normalized_name': nfbc_player['normalized_name'],
            'primary_position': primary_position,
            'position_eligibility': position_eligibility,
            'team': team,
            'team_mismatch': team_mismatch,
            
            # ADP data (from NFBC)
            'adp': {
                'nfbc': nfbc_player['adp'],
                'rank': nfbc_player['rank'],
                'min_pick': nfbc_player['min_pick'],
                'max_pick': nfbc_player['max_pick']
            },
            
            # CBS data (if available)
            'cbs_data': {
                'has_position_data': cbs_position is not None,
                'has_stats_data': cbs_stats is not None
            }
        }
        
        # Add historical stats if available
        if cbs_stats and cbs_stats.get('historical_stats'):
            master_player['historical_stats'] = cbs_stats['historical_stats']
        
        return master_player
    
    def _check_team_mismatches(self, master_players: List[Dict]) -> List[Tuple[str, str, str]]:
        """Check for team mismatches between NFBC and CBS."""
        mismatches = []
        for player in master_players:
            if player.get('team_mismatch'):
                mismatches.append((
                    player['name'],
                    player['team_mismatch']['nfbc'],
                    player['team_mismatch']['cbs']
                ))
        return mismatches
    
    def _save_master_player_dict(self, master_players: List[Dict]):
        """Save master player dictionary."""
        output_file = self.output_dir / "players.json"
        metadata_file = self.output_dir / "metadata.json"
        
        # Save players
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'players': master_players
            }, f, indent=2)
        
        # Save metadata
        from datetime import datetime
        metadata = {
            'source': 'nfbc_adp',
            'load_date': datetime.now().isoformat(),
            'player_count': len(master_players),
            'description': 'Master player dictionary - NFBC ADP as source of truth, CBS data merged',
            'year': 2026
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Saved master player dict: {output_file}")
        print(f"   ✅ Saved metadata: {metadata_file}")
    
    def _safe_float(self, value) -> float:
        """Safely convert to float."""
        if not value or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value) -> int:
        """Safely convert to int."""
        if not value or value == '' or value == '-':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

