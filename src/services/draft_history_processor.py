"""Draft history processor - analyzes historical drafts for value insights."""
import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from src.services.player_matcher import PlayerMatcher


class DraftHistoryProcessor:
    """
    Processes historical draft data to extract:
    - Value by round
    - Position scarcity timing
    - Late-round gems
    - Early-round busts
    - Draft strategy patterns
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.raw_dir = project_root / "raw" / "historical_data"
        self.output_dir = project_root / "data" / "league_analysis" / "draft_history"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.player_matcher = PlayerMatcher()
        self.historical_years = [2021, 2022, 2023, 2024, 2025]
    
    def process_all_drafts(self) -> Dict:
        """
        Process all historical drafts and generate analysis.
        """
        print("=" * 60)
        print("Processing Draft History")
        print("=" * 60)
        
        all_drafts = []
        
        # Load all draft files
        for year in self.historical_years:
            draft_file = self.raw_dir / f"cbs_{year}_draft.csv"
            if draft_file.exists():
                print(f"\nProcessing {year} draft...")
                draft_data = self._load_draft_file(draft_file, year)
                all_drafts.append(draft_data)
                print(f"  Loaded {len(draft_data['picks'])} picks across {draft_data['total_rounds']} rounds")
        
        # Generate analysis
        print("\n" + "=" * 60)
        print("Generating Value Analysis")
        print("=" * 60)
        
        value_analysis = self._analyze_draft_value(all_drafts)
        position_scarcity = self._analyze_position_scarcity(all_drafts)
        draft_strategies = self._analyze_draft_strategies(all_drafts)
        
        # Save outputs
        self._save_drafts(all_drafts)
        self._save_value_analysis(value_analysis)
        self._save_position_scarcity(position_scarcity)
        self._save_draft_strategies(draft_strategies)
        
        print(f"\n✅ Draft history processing complete!")
        print(f"   Processed {len(all_drafts)} drafts")
        print(f"   Total picks analyzed: {sum(len(d['picks']) for d in all_drafts)}")
        
        return {
            'drafts_processed': len(all_drafts),
            'total_picks': sum(len(d['picks']) for d in all_drafts),
            'years': [d['year'] for d in all_drafts]
        }
    
    def _load_draft_file(self, filepath: Path, year: int) -> Dict:
        """Load and parse a draft file."""
        picks = []
        current_round = None
        total_teams = 0
        teams_seen = set()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row in reader:
                if not row:
                    continue
                
                # Check for round header
                if row[0] and row[0].startswith('Round'):
                    current_round = int(row[0].split()[1])
                    continue
                
                # Check for header row
                if row[0] == 'Pick' or row[0] == '':
                    continue
                
                # Parse pick
                if row[0].isdigit():
                    pick_number = int(row[0])
                    team = row[1].strip() if len(row) > 1 else ''
                    player_str = row[2].strip() if len(row) > 2 else ''
                    
                    if not player_str:
                        continue
                    
                    # Parse player string
                    name, position, team_abbrev = self._parse_player_string(player_str)
                    
                    if not name:
                        continue
                    
                    # Track teams
                    teams_seen.add(team)
                    
                    # Use current_round if available, otherwise calculate from pick number
                    if current_round:
                        round_num = current_round
                    elif teams_seen:
                        # Calculate round: pick 1-13 = round 1, pick 14-26 = round 2, etc.
                        round_num = ((pick_number - 1) // len(teams_seen)) + 1
                    else:
                        round_num = 1
                    
                    picks.append({
                        'pick_number': pick_number,
                        'round': round_num,
                        'team': team,
                        'player_name': name,
                        'normalized_name': self.player_matcher.normalize_player_name(name),
                        'position': position,
                        'team_abbrev': team_abbrev,
                        'elapsed_time': row[4].strip() if len(row) > 4 else None
                    })
        
        # Determine total teams and rounds
        total_teams = len(teams_seen) if teams_seen else 13
        total_rounds = max((p['round'] for p in picks), default=1)
        
        return {
            'year': year,
            'total_teams': total_teams,
            'total_rounds': total_rounds,
            'total_picks': len(picks),
            'picks': picks
        }
    
    def _parse_player_string(self, player_str: str) -> Tuple[str, str, str]:
        """Parse player string like 'Ronald Acuna Jr. OF | ATL'."""
        # Remove asterisk (undroppable)
        player_str = player_str.replace('*', '').strip()
        
        # Split by |
        if '|' in player_str:
            parts = player_str.split('|')
            name_part = parts[0].strip()
            team = parts[1].strip() if len(parts) > 1 else None
        else:
            name_part = player_str.strip()
            team = None
        
        # Extract position
        position = None
        valid_positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P', 'DH', 'U']
        
        for pos in valid_positions:
            if name_part.endswith(f' {pos}'):
                position = pos
                name = name_part[:-len(f' {pos}')].strip()
                break
            elif f' {pos} ' in name_part:
                position = pos
                name = name_part.replace(f' {pos} ', ' ').strip()
                break
        
        if not position:
            name = name_part
            position = 'U'
        
        return name, position, team
    
    def _analyze_draft_value(self, all_drafts: List[Dict]) -> Dict:
        """Analyze value by round."""
        print("\nAnalyzing value by round...")
        
        # Group picks by round across all years
        picks_by_round = defaultdict(list)
        for draft in all_drafts:
            for pick in draft['picks']:
                picks_by_round[pick['round']].append({
                    'year': draft['year'],
                    'pick_number': pick['pick_number'],
                    'player': pick['player_name'],
                    'position': pick['position'],
                    'team': pick['team']
                })
        
        # Calculate round statistics
        round_analysis = {}
        for round_num in sorted(picks_by_round.keys()):
            picks = picks_by_round[round_num]
            round_analysis[round_num] = {
                'total_picks': len(picks),
                'positions': self._count_positions(picks),
                'average_pick_number': sum(p['pick_number'] for p in picks) / len(picks) if picks else 0
            }
        
        return {
            'by_round': round_analysis,
            'total_rounds_analyzed': len(round_analysis),
            'years_included': [d['year'] for d in all_drafts]
        }
    
    def _analyze_position_scarcity(self, all_drafts: List[Dict]) -> Dict:
        """Analyze when positions become scarce."""
        print("Analyzing position scarcity...")
        
        position_analysis = {}
        positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P']
        
        for position in positions:
            # Track when this position gets drafted
            rounds_when_drafted = []
            for draft in all_drafts:
                for pick in draft['picks']:
                    if pick['position'] == position:
                        rounds_when_drafted.append(pick['round'])
            
            if rounds_when_drafted:
                position_analysis[position] = {
                    'average_round': sum(rounds_when_drafted) / len(rounds_when_drafted),
                    'median_round': sorted(rounds_when_drafted)[len(rounds_when_drafted) // 2],
                    'first_round': min(rounds_when_drafted),
                    'last_round': max(rounds_when_drafted),
                    'total_picks': len(rounds_when_drafted),
                    'scarcity_round': self._calculate_scarcity_round(rounds_when_drafted)
                }
        
        return position_analysis
    
    def _analyze_draft_strategies(self, all_drafts: List[Dict]) -> Dict:
        """Analyze draft strategies (what winning teams did)."""
        print("Analyzing draft strategies...")
        
        # This will be enhanced when we can match to league results
        # For now, track basic patterns
        
        strategies = {
            'position_distribution': self._analyze_position_distribution(all_drafts),
            'pitcher_timing': self._analyze_pitcher_timing(all_drafts),
            'early_round_patterns': self._analyze_early_round_patterns(all_drafts)
        }
        
        return strategies
    
    def _count_positions(self, picks: List[Dict]) -> Dict[str, int]:
        """Count positions in a set of picks."""
        positions = defaultdict(int)
        for pick in picks:
            positions[pick['position']] += 1
        return dict(positions)
    
    def _calculate_scarcity_round(self, rounds: List[int]) -> int:
        """Calculate when position becomes scarce (75th percentile)."""
        if not rounds:
            return 0
        sorted_rounds = sorted(rounds)
        percentile_75 = int(len(sorted_rounds) * 0.75)
        return sorted_rounds[percentile_75] if percentile_75 < len(sorted_rounds) else sorted_rounds[-1]
    
    def _analyze_position_distribution(self, all_drafts: List[Dict]) -> Dict:
        """Analyze how positions are distributed across rounds."""
        position_by_round = defaultdict(lambda: defaultdict(int))
        
        for draft in all_drafts:
            for pick in draft['picks']:
                position_by_round[pick['round']][pick['position']] += 1
        
        return {str(round_num): dict(positions) for round_num, positions in position_by_round.items()}
    
    def _analyze_pitcher_timing(self, all_drafts: List[Dict]) -> Dict:
        """Analyze when pitchers are typically drafted."""
        pitcher_rounds = []
        hitter_rounds = []
        
        for draft in all_drafts:
            for pick in draft['picks']:
                if pick['position'] in ['SP', 'RP', 'P']:
                    pitcher_rounds.append(pick['round'])
                else:
                    hitter_rounds.append(pick['round'])
        
        return {
            'pitchers': {
                'average_round': sum(pitcher_rounds) / len(pitcher_rounds) if pitcher_rounds else 0,
                'first_pitcher_round': min(pitcher_rounds) if pitcher_rounds else 0
            },
            'hitters': {
                'average_round': sum(hitter_rounds) / len(hitter_rounds) if hitter_rounds else 0
            }
        }
    
    def _analyze_early_round_patterns(self, all_drafts: List[Dict]) -> Dict:
        """Analyze patterns in early rounds (1-5)."""
        early_round_picks = []
        
        for draft in all_drafts:
            for pick in draft['picks']:
                if pick['round'] <= 5:
                    early_round_picks.append(pick)
        
        return {
            'total_early_picks': len(early_round_picks),
            'position_distribution': self._count_positions(early_round_picks),
            'most_drafted_positions': sorted(
                self._count_positions(early_round_picks).items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
    
    def _save_drafts(self, all_drafts: List[Dict]):
        """Save all draft data."""
        output_file = self.output_dir / "drafts.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'drafts': all_drafts,
                'metadata': {
                    'total_drafts': len(all_drafts),
                    'years': [d['year'] for d in all_drafts],
                    'total_picks': sum(len(d['picks']) for d in all_drafts)
                }
            }, f, indent=2)
        print(f"✅ Saved drafts: {output_file}")
    
    def _save_value_analysis(self, value_analysis: Dict):
        """Save value analysis."""
        output_file = self.output_dir / "value_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(value_analysis, f, indent=2)
        print(f"✅ Saved value analysis: {output_file}")
    
    def _save_position_scarcity(self, position_scarcity: Dict):
        """Save position scarcity analysis."""
        output_file = self.output_dir / "position_scarcity.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(position_scarcity, f, indent=2)
        print(f"✅ Saved position scarcity: {output_file}")
    
    def _save_draft_strategies(self, draft_strategies: Dict):
        """Save draft strategies."""
        output_file = self.output_dir / "draft_strategies.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(draft_strategies, f, indent=2)
        print(f"✅ Saved draft strategies: {output_file}")

