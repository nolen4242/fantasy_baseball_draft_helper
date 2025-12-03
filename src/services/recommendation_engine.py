"""AI/ML recommendation engine for draft picks."""
from typing import List, Dict, Tuple, Optional
import numpy as np
from src.models.player import Player
from src.models.draft import DraftState
from src.services.draft_service import DraftService
from src.services.ml_trainer import MLTrainer
from src.services.standings_calculator import StandingsCalculator
from src.services.team_service import TeamService


class RecommendationEngine:
    """Provides AI-powered draft recommendations."""
    
    def __init__(self, draft_service: DraftService, all_players: List[Player] = None):
        self.draft_service = draft_service
        self.ml_trainer = MLTrainer()
        self.standings_calculator = StandingsCalculator()
        self.team_service = TeamService()
        self.all_players = all_players or []
        self._ml_models_loaded = False
    
    def get_recommendations(
        self,
        available_players: List[Player],
        my_team: List[Player],
        draft_state: DraftState,
        top_n: int = 5,
        use_ml: bool = True
    ) -> List[Dict]:
        """
        Get top N draft recommendations.
        RECALCULATES EVERY TIME based on current draft state - recommendations
        update dynamically as picks are made.
        
        Args:
            available_players: List of available players (should be filtered to undrafted)
            my_team: Current roster
            draft_state: Current draft state (includes all picks made so far)
            top_n: Number of recommendations to return
            use_ml: Whether to use ML models (if available)
        
        Returns list of dicts with:
        - player: Player object
        - score: recommendation score
        - reasoning: explanation for the recommendation
        """
        if not available_players:
            return []
        
        # Try to load ML models if not already loaded
        if use_ml and not self._ml_models_loaded:
            self._ml_models_loaded = self.ml_trainer.load_models()
        
        # Get all team rosters for opponent analysis
        all_team_rosters = self._get_all_team_rosters(draft_state)
        
        recommendations = []
        
        # Sort available players by ADP first to prioritize evaluation
        sorted_available = sorted(
            available_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # Evaluate more players (top 200) to ensure we catch pitchers
        # But also ensure we evaluate at least some pitchers even if they're lower ADP
        pitchers = [p for p in sorted_available if p.position in ['SP', 'RP', 'P']]
        hitters = [p for p in sorted_available if p.position not in ['SP', 'RP', 'P']]
        
        # Evaluate top 150 by ADP
        players_to_evaluate = sorted_available[:150]
        
        # Also include top 20 pitchers even if they're not in top 150
        top_pitchers = pitchers[:20]
        for pitcher in top_pitchers:
            if pitcher not in players_to_evaluate:
                players_to_evaluate.append(pitcher)
        
        for player in players_to_evaluate:
            score, reasoning = self._calculate_player_value(
                player, my_team, available_players, draft_state, all_team_rosters, use_ml
            )
            recommendations.append({
                'player': player,
                'score': score,
                'reasoning': reasoning
            })
        
        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return recommendations[:top_n]
    
    def _get_all_team_rosters(self, draft_state: DraftState) -> Dict[str, List[Player]]:
        """Get all team rosters as Player objects."""
        all_rosters = {}
        
        for team_name, player_ids in draft_state.team_rosters.items():
            players = [
                p for p in self.all_players
                if p.player_id in player_ids
            ]
            all_rosters[team_name] = players
        
        return all_rosters
    
    def _calculate_player_value(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]],
        use_ml: bool = True
    ) -> Tuple[float, str]:
        """
        Calculate a value score for a player.
        
        Returns (score, reasoning)
        """
        score = 0.0
        reasoning_parts = []
        
        # 1. ML-based value prediction (if available)
        ml_score = 0.0
        if use_ml and self._ml_models_loaded:
            try:
                pick_number = len(draft_state.picks) + 1
                round_num = draft_state.current_round
                ml_value = self.ml_trainer.predict_player_value(
                    player, my_team, available_players, pick_number, round_num, all_team_rosters
                )
                ml_score = ml_value * 10  # Scale ML prediction
                if ml_score > 0:
                    reasoning_parts.append(f"ML value: {ml_score:.1f}")
            except Exception as e:
                # Fall back to rule-based if ML fails
                pass
        
        # 2. Position scarcity analysis (dynamic, considers what's been drafted)
        position_score, pos_reasoning = self._analyze_position_scarcity(
            player, my_team, available_players, draft_state, all_team_rosters
        )
        score += position_score * 0.25
        if pos_reasoning:
            reasoning_parts.append(pos_reasoning)
        
        # 3. Team needs analysis (prevents redundant picks, balances hitters/pitchers)
        needs_score, needs_reasoning = self._analyze_team_needs(
            player, my_team, draft_state, available_players
        )
        score += needs_score * 0.3
        if needs_reasoning:
            reasoning_parts.append(needs_reasoning)
        
        # 4. Projected value analysis
        value_score, value_reasoning = self._analyze_projected_value(
            player, available_players
        )
        # Scale value score to be more reasonable (divide by 10 to normalize)
        score += (value_score / 10) * 0.2
        if value_reasoning:
            reasoning_parts.append(value_reasoning)
        
        # 5. Relative advantage (vs opponents, considers strategies)
        relative_score, relative_reasoning = self._analyze_relative_advantage(
            player, my_team, all_team_rosters, draft_state, available_players
        )
        score += relative_score * 0.25
        if relative_reasoning:
            reasoning_parts.append(relative_reasoning)
        
        # 6. ADP-based value adjustment (CRITICAL: penalize high ADP players early)
        adp_score, adp_reasoning = self._analyze_adp_value(
            player, draft_state, available_players
        )
        score += adp_score
        if adp_reasoning:
            reasoning_parts.append(adp_reasoning)
        
        # Add ML score
        score += ml_score
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Solid pick"
        
        return score, reasoning
    
    def _analyze_adp_value(
        self,
        player: Player,
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        Analyze ADP value - heavily penalize high ADP players when picking early.
        This prevents recommending players way above their ADP.
        """
        current_pick = len(draft_state.picks) + 1
        player_adp = player.adp
        
        if player_adp is None:
            # No ADP - slight penalty, but not huge
            return -20, "No ADP data"
        
        # Calculate ADP difference (how far off are we?)
        adp_difference = current_pick - player_adp
        
        # If we're picking way before their ADP, that's good (negative difference = good)
        # If we're picking way after their ADP, that's bad (positive difference = bad)
        
        # Early picks (1-50): Heavily penalize players with ADP > current_pick + 20
        if current_pick <= 50:
            if player_adp > current_pick + 20:
                # Way too early for this player
                penalty = -300 - ((player_adp - current_pick) * 5)
                return penalty, f"ADP {player_adp} - WAY TOO EARLY (pick {current_pick})"
            elif player_adp > current_pick + 10:
                # Too early
                penalty = -100 - ((player_adp - current_pick) * 3)
                return penalty, f"ADP {player_adp} - too early (pick {current_pick})"
            elif player_adp < current_pick - 10:
                # Great value - picking someone who should have gone earlier
                bonus = 50 + ((current_pick - player_adp) * 2)
                return bonus, f"ADP {player_adp} - great value!"
            elif player_adp <= current_pick + 5:
                # Reasonable range
                return 0, f"ADP {player_adp} - reasonable"
            else:
                # Slightly early
                return -30, f"ADP {player_adp} - slightly early"
        
        # Mid picks (51-150): Moderate penalties
        elif current_pick <= 150:
            if player_adp > current_pick + 30:
                penalty = -200 - ((player_adp - current_pick) * 3)
                return penalty, f"ADP {player_adp} - too early (pick {current_pick})"
            elif player_adp < current_pick - 20:
                bonus = 30 + ((current_pick - player_adp) * 1.5)
                return bonus, f"ADP {player_adp} - good value"
            else:
                return 0, f"ADP {player_adp} - reasonable"
        
        # Late picks (151+): Less strict
        else:
            if player_adp > current_pick + 50:
                penalty = -100
                return penalty, f"ADP {player_adp} - early"
            elif player_adp < current_pick - 30:
                bonus = 20
                return bonus, f"ADP {player_adp} - value"
            else:
                return 0, f"ADP {player_adp}"
    
    def _analyze_relative_advantage(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        Analyze how much this player helps you vs. opponents.
        Considers opponent strategies and adapts recommendations.
        """
        score = 0.0
        reasoning_parts = []
        
        # Calculate my current category totals
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        
        # Calculate projected totals if I draft this player
        my_projected_roster = my_team + [player]
        my_projected_totals = self.standings_calculator._calculate_team_totals(my_projected_roster)
        
        # Calculate category improvements
        category_improvements = {}
        for category in ['HR', 'R', 'RBI', 'SB', 'W', 'QS', 'K', 'SV', 'HD']:
            improvement = my_projected_totals[category] - my_totals[category]
            category_improvements[category] = improvement
        
        # For OBP, ERA, WHIP - calculate improvement differently
        if player.position not in ['SP', 'RP', 'P']:
            if my_totals['OBP'] > 0:
                obp_improvement = my_projected_totals['OBP'] - my_totals['OBP']
                category_improvements['OBP'] = obp_improvement
        
        # Calculate opponent category totals and strategies
        opponent_totals = {}
        opponent_strategies = {}  # Track if opponents are going heavy hitter/pitcher
        
        for team_name, roster in all_team_rosters.items():
            if team_name == draft_state.my_team_name:
                continue
            totals = self.standings_calculator._calculate_team_totals(roster)
            opponent_totals[team_name] = totals
            
            # Analyze opponent strategy
            opponent_hitters = sum(1 for p in roster if p.position not in ['SP', 'RP', 'P'])
            opponent_pitchers = len(roster) - opponent_hitters
            opponent_strategies[team_name] = {
                'hitters': opponent_hitters,
                'pitchers': opponent_pitchers,
                'ratio': opponent_hitters / max(1, opponent_pitchers)
            }
        
        # Find categories where I'm behind and this player helps
        for category in ['HR', 'R', 'RBI', 'SB', 'W', 'QS', 'K', 'SV', 'HD']:
            my_value = my_totals[category]
            improvement = category_improvements.get(category, 0)
            
            if improvement > 0:
                # Count how many opponents are ahead of me
                opponents_ahead = sum(
                    1 for totals in opponent_totals.values()
                    if totals[category] > my_value
                )
                
                # This player helps me catch up
                if opponents_ahead > 0:
                    score += improvement * (opponents_ahead * 3)
                    reasoning_parts.append(f"+{improvement:.1f} {category} (catch {opponents_ahead} teams)")
        
        # Analyze opponent strategies and adapt
        # If many opponents are going heavy pitchers, maybe prioritize hitters (or vice versa)
        avg_opponent_hitter_ratio = np.mean([s['ratio'] for s in opponent_strategies.values()]) if opponent_strategies else 1.0
        my_hitter_ratio = (len(my_team) - sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])) / max(1, sum(1 for p in my_team if p.position in ['SP', 'RP', 'P']))
        
        is_hitter = player.position not in ['SP', 'RP', 'P']
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        # Count total pitchers/hitters drafted by all teams
        total_pitchers_drafted = sum(
            sum(1 for p in roster if p.position in ['SP', 'RP', 'P'])
            for roster in all_team_rosters.values()
        )
        total_hitters_drafted = sum(
            sum(1 for p in roster if p.position not in ['SP', 'RP', 'P'])
            for roster in all_team_rosters.values()
        )
        
        # If opponents are going heavy pitchers, hitters become more valuable
        if avg_opponent_hitter_ratio < 0.8 and is_hitter:
            score += 30
            reasoning_parts.append(f"Opponents heavy on pitchers ({total_pitchers_drafted} pitchers drafted) - hitters valuable")
        # If opponents are going heavy hitters, pitchers become more valuable
        elif avg_opponent_hitter_ratio > 1.5 and is_pitcher:
            score += 40  # Increased from 20
            reasoning_parts.append(f"Opponents heavy on hitters ({total_hitters_drafted} hitters drafted) - pitchers valuable")
        
        # Early draft: If many pitchers already taken, remaining ones are more valuable
        current_pick = len(draft_state.picks) + 1
        if is_pitcher and current_pick <= 100:
            if total_pitchers_drafted > 40:
                score += 30
                reasoning_parts.append(f"Pitcher run happening ({total_pitchers_drafted} drafted) - get value now")
            elif total_pitchers_drafted < 20 and current_pick > 50:
                # Few pitchers taken, might be undervalued
                score += 25
                reasoning_parts.append(f"Pitchers undervalued ({total_pitchers_drafted} drafted) - good time to draft")
        
        # Blocking value - prevent opponents from getting this player
        # Check which opponents need this position
        position_needed_by_opponents = 0
        critical_opponents = []
        
        for team_name, roster in all_team_rosters.items():
            if team_name == draft_state.my_team_name:
                continue
            
            # Count how many players opponent has at this position
            opponent_count = sum(1 for p in roster if p.position == player.position)
            my_count = sum(1 for p in my_team if p.position == player.position)
            
            # Check if opponent needs this position more than I do
            position_requirements = {'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'OF': 4, 'P': 9}
            required = position_requirements.get(player.position, 1)
            
            if opponent_count < required and opponent_count < my_count:
                position_needed_by_opponents += 1
                critical_opponents.append(team_name)
        
        if position_needed_by_opponents > 0:
            block_score = position_needed_by_opponents * 15
            score += block_score
            reasoning_parts.append(f"Blocks {position_needed_by_opponents} opponent(s) from {player.position}")
        
        # Consider what's been drafted - if many players at this position are gone, it's more valuable
        drafted_at_position = sum(
            1 for team_roster in all_team_rosters.values()
            for p in team_roster
            if p.position == player.position
        )
        
        # If this is a top player and many at this position are gone, higher value
        if player.adp and player.adp < 50 and drafted_at_position > 5:
            score += 15
            reasoning_parts.append(f"Top {player.position} - {drafted_at_position} already drafted")
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else ""
        
        return score, reasoning
    
    def _analyze_position_scarcity(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]]
    ) -> Tuple[float, str]:
        """
        Analyze position scarcity dynamically based on what's been drafted.
        Considers top-heavy vs deep positions.
        UPDATES IN REAL-TIME as picks are made.
        """
        player_pos = player.position
        current_pick = len(draft_state.picks) + 1
        
        # Count how many players at this position have been drafted BY ALL TEAMS
        drafted_at_position = sum(
            1 for team_roster in all_team_rosters.values()
            for p in team_roster
            if p.position == player_pos
        )
        
        # Count available players at this position
        available_at_position = sum(1 for p in available_players if p.position == player_pos)
        
        # Count total players at this position (drafted + available)
        total_at_position = drafted_at_position + available_at_position
        
        if total_at_position == 0:
            return 0.0, ""
        
        # Calculate what % of this position has been drafted
        drafted_percentage = drafted_at_position / total_at_position if total_at_position > 0 else 0
        
        # Calculate how many teams still need this position
        position_requirements = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'OF': 4, 'P': 9, 'SP': 9, 'RP': 9
        }
        required_per_team = position_requirements.get(player_pos, 1)
        total_needed = draft_state.total_teams * required_per_team
        
        # How many slots are still open?
        slots_filled = drafted_at_position
        slots_remaining = max(0, total_needed - slots_filled)
        
        # Calculate scarcity score
        if slots_remaining > 0:
            scarcity_ratio = available_at_position / slots_remaining
        else:
            scarcity_ratio = 0.1  # Very scarce if no slots left
        
        # Top-heavy positions (C, SS) are more valuable early
        # Deep positions (OF, P) can wait
        top_heavy_positions = ['C', 'SS', '2B', '3B']
        is_top_heavy = player_pos in top_heavy_positions
        is_pitcher = player_pos in ['SP', 'RP', 'P']
        
        # Calculate tier-based scarcity
        if is_top_heavy:
            # Check how many elite players (top 20% by ADP) are left
            position_players = [p for p in available_players if p.position == player_pos]
            if position_players:
                sorted_by_adp = sorted(
                    position_players,
                    key=lambda p: (p.adp is None, p.adp or float('inf'))
                )
                elite_threshold = max(1, len(position_players) // 5)  # Top 20%
                elite_remaining = len([p for p in sorted_by_adp[:elite_threshold] if p.adp and p.adp < 100])
                
                # If this is an elite player and few elite remain, high scarcity
                if player.adp and player.adp < 100 and elite_remaining < 3:
                    scarcity_score = 150
                    reasoning = f"Elite {player_pos} - {elite_remaining} elite left, {drafted_at_position} drafted"
                elif player.adp and player.adp < 100:
                    scarcity_score = 100
                    reasoning = f"Elite {player_pos} - {elite_remaining} elite left"
                else:
                    scarcity_score = 50
                    reasoning = f"Mid-tier {player_pos}"
            else:
                scarcity_score = 0
                reasoning = ""
        elif is_pitcher:
            # Pitchers: Consider how many have been drafted
            # If many pitchers drafted, remaining ones become more valuable
            if drafted_at_position > 50:  # Many pitchers already taken
                scarcity_score = 100
                reasoning = f"Pitcher scarcity: {drafted_at_position} drafted, {available_at_position} left"
            elif drafted_at_position > 30:
                scarcity_score = 70
                reasoning = f"Pitcher: {drafted_at_position} drafted, {available_at_position} left"
            elif scarcity_ratio < 1.0:
                scarcity_score = 60
                reasoning = f"Pitcher: {available_at_position} left for {slots_remaining} slots"
            else:
                scarcity_score = 40
                reasoning = f"Pitcher: Deep pool"
        else:
            # Deep positions (OF) - scarcity based on remaining slots
            if scarcity_ratio < 0.5:
                scarcity_score = 80
                reasoning = f"Scarce {player_pos} - {available_at_position} left for {slots_remaining} slots"
            elif scarcity_ratio < 1.0:
                scarcity_score = 50
                reasoning = f"Moderate {player_pos} availability"
            else:
                scarcity_score = 20
                reasoning = f"Deep {player_pos} pool"
        
        # Penalize if position is over-drafted (too many already taken)
        if drafted_percentage > 0.8:
            scarcity_score *= 0.5  # Reduce score if position is mostly gone
            reasoning += " (position mostly drafted)"
        
        # Bonus: If this position is being heavily drafted by others, it's more valuable
        if drafted_at_position > 5 and current_pick < 50:
            scarcity_score += 20
            reasoning += f" (hot position: {drafted_at_position} taken)"
        
        return scarcity_score, reasoning
    
    def _analyze_team_needs(
        self,
        player: Player,
        my_team: List[Player],
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        Analyze if this player fills a team need - Bob Uecker League rules.
        Prevents redundant picks and considers dynamic roster state.
        """
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
        mi_eligible_count = sum(1 for p in my_team if p.position in ['2B', 'SS'])
        ci_eligible_count = sum(1 for p in my_team if p.position in ['1B', '3B'])
        u_eligible_count = sum(1 for p in my_team if p.position not in ['SP', 'RP', 'P'])
        pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        hitter_count = len(my_team) - pitcher_count
        
        player_pos = player.position
        is_hitter = player_pos not in ['SP', 'RP', 'P']
        is_pitcher = player_pos in ['SP', 'RP', 'P']
        
        # Calculate need score
        need_score = 0.0
        reasoning_parts = []
        
        # CRITICAL: Prevent redundant position picks
        # If we already have enough at this position, heavily penalize
        required = position_requirements.get(player_pos, 0)
        if required > 0:
            position_count = position_counts.get(player_pos, 0)
            
            # If we already have enough, this is redundant
            if position_count >= required:
                # Allow 1 extra for depth, but penalize heavily after that
                if position_count > required + 1:
                    need_score -= 200  # Heavy penalty for redundant pick
                    reasoning_parts.append(f"REDUNDANT: Already have {position_count} {player_pos} (need {required})")
                    return need_score, " | ".join(reasoning_parts)
                elif position_count == required + 1:
                    need_score -= 50  # Light penalty for depth
                    reasoning_parts.append(f"Depth pick: {position_count} {player_pos} (need {required})")
            else:
                # We need this position
                need_score += (required - position_count) * 80
                reasoning_parts.append(f"Fills {player_pos} need ({position_count}/{required})")
        
        # Balance hitters vs pitchers dynamically
        # Need 11 hitters (C, 1B, 2B, 3B, SS, MI, CI, 4 OF, U) and 9 pitchers
        total_hitters_needed = 11
        total_pitchers_needed = 9
        
        # Calculate how many picks remain
        picks_remaining = (draft_state.total_teams * draft_state.roster_size) - len(draft_state.picks)
        my_picks_remaining = draft_state.roster_size - len(my_team)
        
        # Calculate ideal hitter/pitcher balance
        hitters_needed = total_hitters_needed - hitter_count
        pitchers_needed = total_pitchers_needed - pitcher_count
        
        # If we're way off balance, prioritize correcting it
        # CRITICAL: Need to balance hitters and pitchers throughout draft
        if is_hitter:
            if hitters_needed > 0:
                # Need hitters - bonus based on how many we need
                need_score += hitters_needed * 20
                if hitters_needed > my_picks_remaining / 2:
                    need_score += 50  # Urgent need
                    reasoning_parts.append(f"URGENT: Need {hitters_needed} more hitters")
                elif hitters_needed > 3:
                    need_score += 30  # Moderate urgency
            else:
                need_score -= 60  # Don't need more hitters
                reasoning_parts.append("Have enough hitters")
        
        if is_pitcher:
            if pitchers_needed > 0:
                # Need pitchers - STRONG bonus (pitchers often undervalued)
                need_score += pitchers_needed * 25  # Increased from 12
                if pitchers_needed > my_picks_remaining / 2:
                    need_score += 80  # Urgent need (increased from 30)
                    reasoning_parts.append(f"URGENT: Need {pitchers_needed} more pitchers")
                elif pitchers_needed > 4:
                    need_score += 50  # Moderate urgency
                    reasoning_parts.append(f"Need {pitchers_needed} more pitchers")
            else:
                need_score -= 60  # Don't need more pitchers
                reasoning_parts.append("Have enough pitchers")
        
        # Early draft: Ensure we get at least some pitchers
        current_pick = len(draft_state.picks) + 1
        if current_pick <= 100:
            # In first ~100 picks, if we have fewer than 3 pitchers, prioritize them
            if is_pitcher and pitcher_count < 3:
                need_score += 40
                reasoning_parts.append(f"Early draft: Building pitcher base ({pitcher_count}/9)")
            # If we have 0 pitchers by pick 50, URGENT
            if is_pitcher and pitcher_count == 0 and current_pick > 40:
                need_score += 100
                reasoning_parts.append("CRITICAL: No pitchers yet!")
        
        # MI eligibility (need 1 MI, can be 2B or SS)
        can_fill_mi = player_pos in ['2B', 'SS']
        if can_fill_mi:
            # Check if we need MI slot
            # Need: 1 dedicated 2B, 1 dedicated SS, AND 1 MI
            has_2b = position_counts.get('2B', 0) > 0
            has_ss = position_counts.get('SS', 0) > 0
            
            if has_2b and has_ss and mi_eligible_count >= 2:
                # Can fill MI slot
                need_score += 40
                reasoning_parts.append("Can fill MI slot")
            elif not has_2b or not has_ss:
                # Still need dedicated 2B or SS first
                need_score += 20
                reasoning_parts.append("Building MI eligibility")
        
        # CI eligibility (need 1 CI, can be 1B or 3B)
        can_fill_ci = player_pos in ['1B', '3B']
        if can_fill_ci:
            has_1b = position_counts.get('1B', 0) > 0
            has_3b = position_counts.get('3B', 0) > 0
            
            if has_1b and has_3b and ci_eligible_count >= 2:
                need_score += 40
                reasoning_parts.append("Can fill CI slot")
            elif not has_1b or not has_3b:
                need_score += 20
                reasoning_parts.append("Building CI eligibility")
        
        # U eligibility (need 1 U, can be any offensive player)
        can_fill_u = is_hitter
        if can_fill_u and hitter_count > 0 and u_eligible_count > 0:
            # Can fill U slot if we have hitters
            need_score += 25
            reasoning_parts.append("Can fill U slot")
        
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

