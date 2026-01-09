"""
Value Over Replacement Player (VORP) Calculator and Opponent Analysis.
Provides advanced draft analytics for better recommendations.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from src.models.player import Player
from src.models.draft import DraftState


@dataclass
class BlockingOpportunity:
    """Represents an opportunity to block an opponent from getting a player."""
    opponent_team: str
    position_needed: str
    positions_filled: int
    positions_required: int
    urgency: float  # 0-1, higher = more urgent need
    impact: str  # Description of blocking impact


@dataclass
class VORPResult:
    """VORP calculation result for a player."""
    player_id: str
    player_name: str
    position: str
    vorp_score: float  # Value over replacement
    replacement_level: Dict[str, float]  # Category values at replacement level
    category_contributions: Dict[str, float]  # How much player exceeds replacement
    tier: str  # "Elite", "Above Average", "Average", "Below Average", "Replacement"


class VORPCalculator:
    """
    Calculates Value Over Replacement Player (VORP) and opponent blocking opportunities.
    Uses historical data and category thresholds to determine player value.
    """
    
    # Position requirements for Bob Uecker League
    POSITION_REQUIREMENTS = {
        'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
        'MI': 1, 'CI': 1, 'OF': 4, 'U': 1, 'P': 9
    }
    
    # MI eligible positions
    MI_ELIGIBLE = ['2B', 'SS']
    # CI eligible positions
    CI_ELIGIBLE = ['1B', '3B']
    # Pitcher positions
    PITCHER_POSITIONS = ['SP', 'RP', 'P']
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        # Load category thresholds
        self.category_thresholds = self._load_category_thresholds()
        self.position_scarcity = self._load_position_scarcity()
        
        # Cache for replacement levels by position
        self._replacement_cache: Dict[str, Dict[str, float]] = {}
    
    def _load_category_thresholds(self) -> Dict:
        """Load category thresholds from JSON."""
        path = self.project_root / "data" / "league_analysis" / "category_thresholds" / "category_thresholds.json"
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_position_scarcity(self) -> Dict:
        """Load position scarcity data from JSON."""
        path = self.project_root / "data" / "league_analysis" / "draft_history" / "position_scarcity.json"
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}
    
    def calculate_replacement_level(
        self,
        position: str,
        available_players: List[Player]
    ) -> Dict[str, float]:
        """
        Calculate replacement level stats for a position.
        Replacement level = average of players ranked 15-25 at that position (deep bench players).
        """
        cache_key = f"{position}_{len(available_players)}"
        if cache_key in self._replacement_cache:
            return self._replacement_cache[cache_key]
        
        # Get players at this position
        is_pitcher = position in self.PITCHER_POSITIONS
        if is_pitcher:
            position_players = [p for p in available_players if p.position in self.PITCHER_POSITIONS]
        else:
            position_players = [p for p in available_players if p.position == position]
        
        if not position_players:
            return {}
        
        # Sort by ADP (best players first)
        sorted_players = sorted(
            position_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # Replacement level = average of players ranked 15-25 (or 60-80 for pitchers)
        if is_pitcher:
            start_idx = min(60, len(sorted_players) - 1)
            end_idx = min(80, len(sorted_players))
        else:
            start_idx = min(15, len(sorted_players) - 1)
            end_idx = min(25, len(sorted_players))
        
        replacement_players = sorted_players[start_idx:end_idx]
        
        if not replacement_players:
            replacement_players = sorted_players[-5:] if len(sorted_players) >= 5 else sorted_players
        
        # Calculate average stats at replacement level
        replacement_level = {}
        
        if is_pitcher:
            categories = ['projected_wins', 'projected_quality_starts', 'projected_strikeouts',
                         'projected_era', 'projected_whip', 'projected_saves', 'projected_holds']
        else:
            categories = ['projected_home_runs', 'projected_runs', 'projected_rbi',
                         'projected_stolen_bases', 'projected_obp']
        
        for cat in categories:
            values = [getattr(p, cat) for p in replacement_players if getattr(p, cat) is not None]
            if values:
                replacement_level[cat] = sum(values) / len(values)
            else:
                replacement_level[cat] = 0.0
        
        self._replacement_cache[cache_key] = replacement_level
        return replacement_level
    
    def calculate_vorp(
        self,
        player: Player,
        available_players: List[Player]
    ) -> VORPResult:
        """
        Calculate Value Over Replacement Player for a single player.
        Higher VORP = more valuable compared to replacement level alternatives.
        """
        position = player.position
        is_pitcher = position in self.PITCHER_POSITIONS
        
        replacement_level = self.calculate_replacement_level(position, available_players)
        
        # Calculate how much this player exceeds replacement level
        category_contributions = {}
        total_vorp = 0.0
        
        if is_pitcher:
            # Pitching categories (K, W, QS contribute positively; ERA, WHIP lower is better)
            if player.projected_strikeouts:
                diff = player.projected_strikeouts - replacement_level.get('projected_strikeouts', 0)
                category_contributions['K'] = diff
                total_vorp += diff * 0.1  # Weight strikeouts
            
            if player.projected_wins:
                diff = player.projected_wins - replacement_level.get('projected_wins', 0)
                category_contributions['W'] = diff
                total_vorp += diff * 2.0
            
            if player.projected_quality_starts:
                diff = player.projected_quality_starts - replacement_level.get('projected_quality_starts', 0)
                category_contributions['QS'] = diff
                total_vorp += diff * 2.0
            
            if player.projected_saves:
                diff = player.projected_saves - replacement_level.get('projected_saves', 0)
                category_contributions['SV'] = diff
                total_vorp += diff * 3.0  # Saves are scarce
            
            if player.projected_holds:
                diff = player.projected_holds - replacement_level.get('projected_holds', 0)
                category_contributions['HLD'] = diff
                total_vorp += diff * 1.5
            
            # ERA and WHIP - lower is better
            if player.projected_era and replacement_level.get('projected_era'):
                diff = replacement_level['projected_era'] - player.projected_era
                category_contributions['ERA'] = diff
                total_vorp += diff * 15  # ERA impact is significant
            
            if player.projected_whip and replacement_level.get('projected_whip'):
                diff = replacement_level['projected_whip'] - player.projected_whip
                category_contributions['WHIP'] = diff
                total_vorp += diff * 30
        else:
            # Batting categories
            if player.projected_home_runs:
                diff = player.projected_home_runs - replacement_level.get('projected_home_runs', 0)
                category_contributions['HR'] = diff
                total_vorp += diff * 2.5
            
            if player.projected_runs:
                diff = player.projected_runs - replacement_level.get('projected_runs', 0)
                category_contributions['R'] = diff
                total_vorp += diff * 0.6
            
            if player.projected_rbi:
                diff = player.projected_rbi - replacement_level.get('projected_rbi', 0)
                category_contributions['RBI'] = diff
                total_vorp += diff * 0.6
            
            if player.projected_stolen_bases:
                diff = player.projected_stolen_bases - replacement_level.get('projected_stolen_bases', 0)
                category_contributions['SB'] = diff
                total_vorp += diff * 3.5  # SBs are scarce
            
            if player.projected_obp:
                diff = player.projected_obp - replacement_level.get('projected_obp', 0.300)
                category_contributions['OBP'] = diff
                total_vorp += diff * 500  # OBP has small range but big impact
        
        # Determine tier based on VORP
        if total_vorp >= 80:
            tier = "Elite"
        elif total_vorp >= 50:
            tier = "Above Average"
        elif total_vorp >= 20:
            tier = "Average"
        elif total_vorp >= 0:
            tier = "Below Average"
        else:
            tier = "Replacement"
        
        return VORPResult(
            player_id=player.player_id,
            player_name=player.name,
            position=position,
            vorp_score=total_vorp,
            replacement_level=replacement_level,
            category_contributions=category_contributions,
            tier=tier
        )
    
    def analyze_opponent_needs(
        self,
        draft_state: DraftState,
        all_players: List[Player]
    ) -> Dict[str, Dict[str, int]]:
        """
        Analyze what positions each opponent team still needs.
        Returns dict of team_name -> {position: slots_needed}
        """
        opponent_needs = {}
        my_team = draft_state.my_team_name
        
        for team_name, player_ids in draft_state.team_rosters.items():
            if team_name == my_team:
                continue
            
            # Count positions on this team
            position_counts = {'C': 0, '1B': 0, '2B': 0, '3B': 0, 'SS': 0, 'OF': 0, 'P': 0}
            
            for pid in player_ids:
                player = next((p for p in all_players if p.player_id == pid), None)
                if player:
                    pos = player.position
                    if pos in self.PITCHER_POSITIONS:
                        position_counts['P'] += 1
                    elif pos in position_counts:
                        position_counts[pos] += 1
            
            # Calculate needs
            needs = {}
            for pos, required in [('C', 1), ('1B', 1), ('2B', 1), ('3B', 1), ('SS', 1), ('OF', 4), ('P', 9)]:
                needed = required - position_counts.get(pos, 0)
                if needed > 0:
                    needs[pos] = needed
            
            opponent_needs[team_name] = needs
        
        return opponent_needs
    
    def find_blocking_opportunities(
        self,
        player: Player,
        draft_state: DraftState,
        all_players: List[Player],
        opponent_needs: Dict[str, Dict[str, int]] = None
    ) -> List[BlockingOpportunity]:
        """
        Find which opponents would be blocked if you draft this player.
        """
        if opponent_needs is None:
            opponent_needs = self.analyze_opponent_needs(draft_state, all_players)
        
        blocking_opportunities = []
        player_pos = player.position
        is_pitcher = player_pos in self.PITCHER_POSITIONS
        
        # Get all available players at this position
        if is_pitcher:
            available_at_pos = [p for p in all_players 
                               if p.position in self.PITCHER_POSITIONS 
                               and not p.drafted 
                               and p.player_id != player.player_id]
        else:
            available_at_pos = [p for p in all_players 
                               if p.position == player_pos 
                               and not p.drafted 
                               and p.player_id != player.player_id]
        
        # Sort by ADP to identify top players
        available_sorted = sorted(
            available_at_pos,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # Check if this player is a top option at this position
        player_rank = next(
            (i for i, p in enumerate(available_sorted) if p.player_id == player.player_id),
            len(available_sorted)
        )
        
        # Only consider blocking if player is in top 20% of available at position
        is_top_player = player_rank < len(available_sorted) * 0.2 if available_sorted else False
        
        for team_name, needs in opponent_needs.items():
            # Check if opponent needs this position
            check_pos = 'P' if is_pitcher else player_pos
            
            if check_pos in needs and needs[check_pos] > 0:
                # Calculate urgency based on how many they need vs available
                positions_needed = needs[check_pos]
                positions_required = self.POSITION_REQUIREMENTS.get(check_pos, 1)
                filled = positions_required - positions_needed
                
                # Higher urgency if:
                # - They need multiple at this position
                # - Few quality options remain
                # - This is a top player at the position
                if is_top_player:
                    remaining_top = len([p for p in available_sorted[:10] if p.player_id != player.player_id])
                    urgency = min(1.0, (positions_needed / positions_required) + (1.0 - remaining_top / 10))
                else:
                    urgency = positions_needed / positions_required * 0.5
                
                if urgency > 0.3:  # Only report significant blocking opportunities
                    impact = f"Blocks {team_name} from getting a top {check_pos}"
                    if positions_needed > 1:
                        impact += f" (they need {positions_needed} more)"
                    
                    blocking_opportunities.append(BlockingOpportunity(
                        opponent_team=team_name,
                        position_needed=check_pos,
                        positions_filled=filled,
                        positions_required=positions_required,
                        urgency=urgency,
                        impact=impact
                    ))
        
        # Sort by urgency (highest first)
        blocking_opportunities.sort(key=lambda x: x.urgency, reverse=True)
        return blocking_opportunities
    
    def get_scarcity_tier(
        self,
        position: str,
        available_players: List[Player],
        draft_state: DraftState
    ) -> Tuple[str, int]:
        """
        Determine the scarcity tier for a position.
        Returns (tier_name, remaining_elite_count)
        """
        is_pitcher = position in self.PITCHER_POSITIONS
        
        if is_pitcher:
            position_players = [p for p in available_players 
                               if p.position in self.PITCHER_POSITIONS and not p.drafted]
        else:
            position_players = [p for p in available_players 
                               if p.position == position and not p.drafted]
        
        # Sort by ADP
        sorted_players = sorted(
            position_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # Define tiers
        total = len(sorted_players)
        elite_count = len([p for p in sorted_players if p.adp and p.adp < 50])
        good_count = len([p for p in sorted_players if p.adp and 50 <= p.adp < 100])
        
        # Get historical scarcity round for this position
        scarcity_data = self.position_scarcity.get(position, {})
        scarcity_round = scarcity_data.get('scarcity_round', 15)
        current_round = draft_state.current_round
        
        if elite_count == 0:
            tier = "Dried Up"
        elif elite_count <= 3:
            tier = "Critical"
        elif elite_count <= 6:
            tier = "Scarce"
        elif current_round >= scarcity_round - 2:
            tier = "Thinning"
        else:
            tier = "Available"
        
        return tier, elite_count
    
    def calculate_category_gap_score(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]]
    ) -> Dict[str, float]:
        """
        Calculate how much this player helps close gaps in each category.
        Compares your team's totals to the league leaders.
        """
        from src.services.standings_calculator import StandingsCalculator
        
        calculator = StandingsCalculator()
        
        # Get my current totals
        my_totals = calculator._calculate_team_totals(my_team)
        
        # Get totals if I add this player
        projected_totals = calculator._calculate_team_totals(my_team + [player])
        
        # Get leader values for each category
        leader_values = {}
        for team_name, roster in all_team_rosters.items():
            team_totals = calculator._calculate_team_totals(roster)
            for cat, val in team_totals.items():
                if cat not in leader_values:
                    leader_values[cat] = val
                elif cat in ['ERA', 'WHIP']:  # Lower is better
                    if val > 0 and (leader_values[cat] == 0 or val < leader_values[cat]):
                        leader_values[cat] = val
                else:
                    leader_values[cat] = max(leader_values[cat], val)
        
        # Calculate gap scores
        gap_scores = {}
        is_pitcher = player.position in self.PITCHER_POSITIONS
        
        if is_pitcher:
            categories = ['K', 'W', 'QS', 'SV', 'HD', 'ERA', 'WHIP']
        else:
            categories = ['HR', 'R', 'RBI', 'SB', 'OBP']
        
        for cat in categories:
            my_val = my_totals.get(cat, 0)
            projected_val = projected_totals.get(cat, 0)
            leader_val = leader_values.get(cat, 0)
            
            if leader_val == 0:
                gap_scores[cat] = 0.0
                continue
            
            if cat in ['ERA', 'WHIP']:  # Lower is better
                # Gap = how much worse we are than leader
                current_gap = my_val - leader_val if my_val > 0 else 0
                projected_gap = projected_val - leader_val if projected_val > 0 else 0
                # Improvement = reduction in gap (positive is good)
                gap_scores[cat] = current_gap - projected_gap
            else:
                # Gap = how much behind leader
                current_gap = leader_val - my_val
                projected_gap = leader_val - projected_val
                # Improvement = reduction in gap (positive is good)
                gap_scores[cat] = current_gap - projected_gap
        
        return gap_scores
    
    def get_rounds_since_position_drafted(
        self,
        position: str,
        draft_state: DraftState,
        all_players: List[Player]
    ) -> int:
        """
        Calculate how many rounds since someone drafted this position.
        Returns 0 if drafted this round, higher = longer since drafted.
        """
        is_pitcher = position in self.PITCHER_POSITIONS
        
        # Go through picks in reverse order
        current_round = draft_state.current_round
        
        for pick in reversed(draft_state.picks):
            player = next((p for p in all_players if p.player_id == pick.player_id), None)
            if player:
                if is_pitcher and player.position in self.PITCHER_POSITIONS:
                    return current_round - pick.round
                elif not is_pitcher and player.position == position:
                    return current_round - pick.round
        
        # Never drafted
        return current_round
