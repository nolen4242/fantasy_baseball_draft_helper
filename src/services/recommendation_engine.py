"""AI/ML recommendation engine for draft picks."""
from typing import List, Dict, Tuple
import numpy as np
from src.models.player import Player
from src.models.draft import DraftState
from src.services.draft_service import DraftService


class RecommendationEngine:
    """Provides AI-powered draft recommendations."""
    
    def __init__(self, draft_service: DraftService):
        self.draft_service = draft_service
    
    def get_recommendations(
        self,
        available_players: List[Player],
        my_team: List[Player],
        draft_state: DraftState,
        top_n: int = 5
    ) -> List[Dict]:
        """
        Get top N draft recommendations.
        
        Returns list of dicts with:
        - player: Player object
        - score: recommendation score
        - reasoning: explanation for the recommendation
        """
        if not available_players:
            return []
        
        recommendations = []
        
        for player in available_players:
            score, reasoning = self._calculate_player_value(
                player, my_team, available_players, draft_state
            )
            recommendations.append({
                'player': player,
                'score': score,
                'reasoning': reasoning
            })
        
        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return recommendations[:top_n]
    
    def _calculate_player_value(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState
    ) -> Tuple[float, str]:
        """
        Calculate a value score for a player.
        
        Returns (score, reasoning)
        """
        score = 0.0
        reasoning_parts = []
        
        # 1. Position scarcity analysis
        position_score, pos_reasoning = self._analyze_position_scarcity(
            player, my_team, available_players
        )
        score += position_score * 0.3
        if pos_reasoning:
            reasoning_parts.append(pos_reasoning)
        
        # 2. Team needs analysis
        needs_score, needs_reasoning = self._analyze_team_needs(
            player, my_team, draft_state
        )
        score += needs_score * 0.3
        if needs_reasoning:
            reasoning_parts.append(needs_reasoning)
        
        # 3. Projected value analysis
        value_score, value_reasoning = self._analyze_projected_value(
            player, available_players
        )
        score += value_score * 0.4
        if value_reasoning:
            reasoning_parts.append(value_reasoning)
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Solid pick"
        
        return score, reasoning
    
    def _analyze_position_scarcity(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """Analyze how scarce this position is."""
        # Count available players at this position
        position_available = sum(1 for p in available_players if p.position == player.position)
        total_available = len(available_players)
        
        if total_available == 0:
            return 0.0, ""
        
        scarcity_ratio = position_available / total_available
        
        # Lower ratio = more scarce = higher score
        score = (1.0 - scarcity_ratio) * 100
        
        if scarcity_ratio < 0.1:
            reasoning = f"Very scarce {player.position} position"
        elif scarcity_ratio < 0.2:
            reasoning = f"Scarce {player.position} position"
        else:
            reasoning = f"Moderate {player.position} availability"
        
        return score, reasoning
    
    def _analyze_team_needs(
        self,
        player: Player,
        my_team: List[Player],
        draft_state: DraftState
    ) -> Tuple[float, str]:
        """Analyze if this player fills a team need - Bob Uecker League rules."""
        # Bob Uecker League position requirements:
        # 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P
        position_requirements = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
            'MI': 1,  # Middle Infielder (2B or SS)
            'CI': 1,  # Corner Infielder (1B or 3B)
            'OF': 4, 'U': 1,  # Utility (any offensive position)
            'SP': 9, 'RP': 9, 'P': 9  # Any combination of pitchers
        }
        
        # Count current players at each position on my team
        position_counts = {}
        for pos in ['C', '1B', '2B', '3B', 'SS', 'MI', 'CI', 'OF', 'U', 'SP', 'RP', 'P']:
            position_counts[pos] = sum(1 for p in my_team if p.position == pos)
        
        # Count players that can fill flexible positions
        # MI can be filled by 2B or SS (but we need at least one dedicated 2B and one SS first)
        mi_eligible_count = sum(1 for p in my_team if p.position in ['2B', 'SS'])
        # CI can be filled by 1B or 3B (but we need at least one dedicated 1B and one 3B first)
        ci_eligible_count = sum(1 for p in my_team if p.position in ['1B', '3B'])
        # U can be filled by any offensive player
        u_eligible_count = sum(1 for p in my_team if p.position not in ['SP', 'RP', 'P'])
        pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        
        # Check if player can fill MI, CI, or U slots
        can_fill_mi = player.position in ['2B', 'SS']
        can_fill_ci = player.position in ['1B', '3B']
        can_fill_u = player.position not in ['SP', 'RP', 'P']
        
        # Calculate need score
        need_score = 0.0
        reasoning_parts = []
        
        # Direct position match (for specific positions like C, 1B, 2B, 3B, SS, OF)
        required = position_requirements.get(player.position, 0)
        if required > 0:
            position_count = position_counts.get(player.position, 0)
            if position_count < required:
                need_score += (required - position_count) * 50
                reasoning_parts.append(f"Fills {player.position} need ({position_count}/{required})")
            else:
                need_score += max(0, 10 - (position_count - required) * 2)
                reasoning_parts.append(f"Depth at {player.position} ({position_count}/{required})")
        
        # MI eligibility (need 1 MI, can be 2B or SS)
        # We need MI if: we have 2B+SS players but haven't filled the MI slot yet
        # OR if we're short on 2B/SS players
        if can_fill_mi:
            # Check if we need the MI slot filled
            # MI slot is separate from 2B and SS - we need 1 dedicated 2B, 1 dedicated SS, AND 1 MI
            if position_counts.get('MI', 0) == 0:
                # We can use a 2B or SS to fill MI if we have extras
                if mi_eligible_count > 2:  # Already have 2B and SS filled
                    need_score += 35
                    reasoning_parts.append(f"Can fill MI slot")
                elif mi_eligible_count >= 1:  # Have at least one, can use for MI
                    need_score += 25
                    reasoning_parts.append(f"Can fill MI slot")
        
        # CI eligibility (need 1 CI, can be 1B or 3B)
        if can_fill_ci:
            if position_counts.get('CI', 0) == 0:
                if ci_eligible_count > 2:  # Already have 1B and 3B filled
                    need_score += 35
                    reasoning_parts.append(f"Can fill CI slot")
                elif ci_eligible_count >= 1:  # Have at least one, can use for CI
                    need_score += 25
                    reasoning_parts.append(f"Can fill CI slot")
        
        # U eligibility (need 1 U, can be any offensive player)
        if can_fill_u:
            if position_counts.get('U', 0) == 0:
                # We have offensive players but haven't filled U slot
                need_score += 25
                reasoning_parts.append(f"Can fill U slot")
        
        # Pitching (need 9 P, any combination)
        if player.position in ['SP', 'RP', 'P']:
            if pitcher_count < position_requirements['P']:
                need_score += (position_requirements['P'] - pitcher_count) * 6
                reasoning_parts.append(f"Fills P need ({pitcher_count}/{position_requirements['P']})")
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Depth pick"
        
        return need_score, reasoning
    
    def _analyze_projected_value(
        self,
        player: Player,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        Analyze projected statistical value based on Bob Uecker League categories.
        Batting: HR, OBP, R, RBI, SB
        Pitching: ERA, K, SHOLDS (Saves + Holds x0.5), WHIP, WQS (Wins + Quality Starts)
        """
        value = 0.0
        
        # Determine if player is a hitter or pitcher
        is_hitter = player.position not in ['SP', 'RP', 'P']
        
        if is_hitter:
            # Batting categories: HR, OBP, R, RBI, SB
            if player.projected_home_runs:
                value += player.projected_home_runs * 2.5  # HR are valuable
            if player.projected_obp:
                # OBP typically ranges 0.300-0.400, scale appropriately
                value += (player.projected_obp - 0.300) * 500  # Higher OBP = better
            if player.projected_runs:
                value += player.projected_runs * 0.6
            if player.projected_rbi:
                value += player.projected_rbi * 0.6
            if player.projected_stolen_bases:
                value += player.projected_stolen_bases * 3.5  # SB are scarce and valuable
        else:
            # Pitching categories: ERA, K, SHOLDS, WHIP, WQS
            if player.projected_wins:
                value += player.projected_wins * 2.0
            if player.projected_quality_starts:
                value += player.projected_quality_starts * 2.0  # WQS = Wins + QS
            if player.projected_strikeouts:
                value += player.projected_strikeouts * 0.25  # K are valuable
            if player.projected_saves:
                value += player.projected_saves * 3.0
            if player.projected_holds:
                # SHOLDS = Saves + Holds x0.5
                value += player.projected_holds * 1.5
            if player.projected_era:
                # Lower ERA is better (typical range 2.50-5.00)
                # Invert: better ERA = higher value
                value += max(0, (5.0 - player.projected_era) * 15)
            if player.projected_whip:
                # Lower WHIP is better (typical range 1.00-1.50)
                value += max(0, (1.5 - player.projected_whip) * 30)
        
        # Compare to available players at same position
        position_peers = [p for p in available_players if p.position == player.position]
        if position_peers:
            peer_values = []
            for peer in position_peers:
                peer_val = 0.0
                peer_is_hitter = peer.position not in ['SP', 'RP', 'P']
                
                if peer_is_hitter:
                    if peer.projected_home_runs:
                        peer_val += peer.projected_home_runs * 2.5
                    if peer.projected_obp:
                        peer_val += (peer.projected_obp - 0.300) * 500
                    if peer.projected_runs:
                        peer_val += peer.projected_runs * 0.6
                    if peer.projected_rbi:
                        peer_val += peer.projected_rbi * 0.6
                    if peer.projected_stolen_bases:
                        peer_val += peer.projected_stolen_bases * 3.5
                else:
                    if peer.projected_wins:
                        peer_val += peer.projected_wins * 2.0
                    if peer.projected_quality_starts:
                        peer_val += peer.projected_quality_starts * 2.0
                    if peer.projected_strikeouts:
                        peer_val += peer.projected_strikeouts * 0.25
                    if peer.projected_saves:
                        peer_val += peer.projected_saves * 3.0
                    if peer.projected_holds:
                        peer_val += peer.projected_holds * 1.5
                    if peer.projected_era:
                        peer_val += max(0, (5.0 - peer.projected_era) * 15)
                    if peer.projected_whip:
                        peer_val += max(0, (1.5 - peer.projected_whip) * 30)
                
                peer_values.append(peer_val)
            
            if peer_values:
                percentile = (sum(1 for v in peer_values if v < value) / len(peer_values)) * 100
                if percentile >= 85:
                    reasoning = f"Elite {player.position} (top {100-percentile:.0f}%)"
                elif percentile >= 70:
                    reasoning = f"Top tier {player.position} (top {100-percentile:.0f}%)"
                elif percentile >= 50:
                    reasoning = f"Solid {player.position} value"
                else:
                    reasoning = f"Average {player.position} value"
            else:
                reasoning = "Good projected value"
        else:
            reasoning = "Good projected value"
        
        return value, reasoning

