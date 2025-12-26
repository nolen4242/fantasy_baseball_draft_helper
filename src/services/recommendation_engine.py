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
    
        # Caching for performance
        self._cache = {}  # Cache key: (player_id, draft_state_hash) -> score
        self._cache_draft_state_hash = None
    
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
        return self.get_recommendations_for_team(
            available_players=available_players,
            team_players=my_team,
            draft_state=draft_state,
            team_name=draft_state.my_team_name,
            top_n=top_n,
            use_ml=use_ml
        )
    
    def get_recommendations_for_team(
        self,
        available_players: List[Player],
        team_players: List[Player],
        draft_state: DraftState,
        team_name: str,
        top_n: int = 5,
        use_ml: bool = True,
        is_auto_draft: bool = False
    ) -> List[Dict]:
        """
        Get top N draft recommendations for a specific team.
        RECALCULATES EVERY TIME based on current draft state - recommendations
        update dynamically as picks are made.
        
        Args:
            available_players: List of available players (should be filtered to undrafted)
            team_players: Current roster for the team
            draft_state: Current draft state (includes all picks made so far)
            team_name: Name of the team to get recommendations for
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
        
        # Batch standings calculations: Calculate once, reuse across all player evaluations
        # This avoids recalculating standings for every player evaluation
        all_team_totals = {}
        for team_name, roster in all_team_rosters.items():
            all_team_totals[team_name] = self.standings_calculator._calculate_team_totals(roster)
        
        recommendations = []
        
        # Sort available players by ADP first to prioritize evaluation
        sorted_available = sorted(
            available_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # For auto-draft: evaluate fewer players (top 50) for speed
        # For user recommendations: evaluate more players (top 150-200) for accuracy
        if is_auto_draft:
            # Auto-draft: Only evaluate top 50 by ADP (faster)
            players_to_evaluate = sorted_available[:50]
            
            # Also include top 10 pitchers even if they're not in top 50
            pitchers = [p for p in sorted_available if p.position in ['SP', 'RP', 'P']]
            top_pitchers = pitchers[:10]
            for pitcher in top_pitchers:
                if pitcher not in players_to_evaluate:
                    players_to_evaluate.append(pitcher)
        else:
            # User recommendations: Evaluate more players (top 150-200) to ensure we catch pitchers
            pitchers = [p for p in sorted_available if p.position in ['SP', 'RP', 'P']]
            hitters = [p for p in sorted_available if p.position not in ['SP', 'RP', 'P']]
            
            # Evaluate top 150 by ADP
            players_to_evaluate = sorted_available[:150]
            
            # Also include top 20 pitchers even if they're not in top 150
            top_pitchers = pitchers[:20]
            for pitcher in top_pitchers:
                if pitcher not in players_to_evaluate:
                    players_to_evaluate.append(pitcher)
        
        # Filter out players that don't have available roster slots
        players_with_slots = []
        for player in players_to_evaluate:
            try:
                has_slot = self.team_service.has_available_slot_for_player(team_name, player)
                if has_slot:
                    players_with_slots.append(player)
            except Exception as e:
                print(f"ERROR checking slot for {player.name}: {e}")
                # Continue anyway - assume slot is available if check fails
                players_with_slots.append(player)
        
        # If we don't have enough players with available slots, expand search
        if len(players_with_slots) < top_n * 2:
            # Expand to more players and filter again
            expanded_evaluate = sorted_available[:300]  # Check top 300
            for player in expanded_evaluate:
                if player not in players_to_evaluate:
                    try:
                        if self.team_service.has_available_slot_for_player(team_name, player):
                        players_with_slots.append(player)
                        if len(players_with_slots) >= top_n * 3:  # Get at least 3x top_n options
                                break
                    except Exception as e:
                        print(f"ERROR checking slot for {player.name} (expanded): {e}")
                        pass
                        players_with_slots.append(player)
                        if len(players_with_slots) >= top_n * 3:
                            break
        
        # If no players have available slots, return empty recommendations
        if not players_with_slots:
            print(f"WARNING: No players with available slots found for {team_name}. Evaluated {len(players_to_evaluate)} players.")
            return []
        
        # Generate draft state hash for caching
        draft_state_hash = self._get_draft_state_hash(draft_state)
        
        # Check if we need to clear cache (draft state changed)
        if draft_state_hash != self._cache_draft_state_hash:
            self._cache.clear()
            self._cache_draft_state_hash = draft_state_hash
        
        # Calculate scores with caching
        for player in players_with_slots:
            cache_key = (player.player_id, draft_state_hash)
            
            # Check cache first
            if cache_key in self._cache:
                score, reasoning = self._cache[cache_key]
            else:
                score, reasoning = self._calculate_player_value(
                    player, team_players, available_players, draft_state, all_team_rosters, use_ml, team_name,
                    is_auto_draft=is_auto_draft, all_team_totals=all_team_totals
                )
                # Cache the result
                self._cache[cache_key] = (score, reasoning)
            
            recommendations.append({
                'player': player,
                'score': score,
                'reasoning': reasoning
            })
        
        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        # Debug: Print score ranges
        if recommendations:
            scores = [r['score'] for r in recommendations]
            top_3_names = [f"{r['player'].name}: {r['score']:.1f}" for r in recommendations[:3]]
            print(f"DEBUG: Recommendation scores - Min: {min(scores):.1f}, Max: {max(scores):.1f}, Top 3: {top_3_names}")
        else:
            print("DEBUG: No recommendations generated - all players may have been filtered out or have negative scores")
        
        # Apply lookahead simulation to top candidates (skip for auto-draft for speed)
        if not is_auto_draft and len(recommendations) >= top_n:
            top_candidates = recommendations[:top_n * 2]  # Consider top 2x for lookahead
            lookahead_scores = self._simulate_lookahead(
                top_candidates, team_players, available_players, draft_state, all_team_rosters, team_name
            )
            
            # Adjust scores based on lookahead
            for rec in recommendations:
                if rec['player'].player_id in lookahead_scores:
                    rec['score'] += lookahead_scores[rec['player'].player_id] * 0.1  # 10% weight on lookahead
                    rec['reasoning'] += f" | Lookahead: {lookahead_scores[rec['player'].player_id]:+.1f}"
            
            # Re-sort after lookahead adjustment
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
    
    def _get_draft_state_hash(self, draft_state: DraftState) -> str:
        """Generate hash of draft state for caching."""
        import hashlib
        # Hash based on picks made (player IDs and order)
        picks_str = ",".join([f"{p.player_id}:{p.team_name}" for p in draft_state.picks[-50:]])  # Last 50 picks
        return hashlib.md5(picks_str.encode()).hexdigest()[:16]
    
    def _simulate_lookahead(
        self,
        candidates: List[Dict],
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]],
        team_name: str
    ) -> Dict[str, float]:
        """
        Simulate next few picks to see which player gives best future position.
        Returns dict of player_id -> lookahead score.
        """
        lookahead_scores = {}
        
        # Simulate next 3-5 picks
        num_simulations = min(5, len(available_players) // 10)  # Don't simulate too far ahead
        
        for candidate in candidates[:10]:  # Only lookahead on top 10 candidates
            player = candidate['player']
            lookahead_score = 0.0
            
            # Simulate drafting this player
            simulated_my_team = my_team + [player]
            simulated_available = [p for p in available_players if p.player_id != player.player_id]
            
            # Simulate next few picks by opponents (they'll likely take best ADP)
            simulated_available_sorted = sorted(
                simulated_available,
                key=lambda p: (p.adp is None, p.adp or float('inf'))
            )
            
            # Simulate opponents taking top ADP players
            picks_until_my_turn = 12  # 13 teams - 1 (me) = 12 picks until my next turn
            simulated_drafted = simulated_available_sorted[:picks_until_my_turn]
            simulated_remaining = simulated_available_sorted[picks_until_my_turn:]
            
            # After simulation, what's my best option?
            if simulated_remaining:
                # Get recommendations for simulated state
                simulated_draft_state = draft_state  # Use current state (simplified)
                best_next_option_score = 0.0
                
                # Evaluate top 5 remaining players
                for next_player in simulated_remaining[:5]:
                    next_score, _ = self._calculate_player_value(
                        next_player, simulated_my_team, simulated_remaining,
                        simulated_draft_state, all_team_rosters, True, team_name
                    )
                    best_next_option_score = max(best_next_option_score, next_score)
                
                # Lookahead score = how good is my next pick after this one?
                lookahead_score = best_next_option_score * 0.3  # 30% weight on future position
            
            lookahead_scores[player.player_id] = lookahead_score
        
        return lookahead_scores
    
    def _predict_opponent_picks(
        self,
        available_players: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        num_picks: int = 12
    ) -> List[Player]:
        """
        Predict what opponents will draft in next few picks.
        Uses ADP + their team needs.
        """
        predicted_picks = []
        sorted_available = sorted(
            available_players,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        
        # Simple prediction: opponents take best ADP available
        # Could be improved with opponent-specific modeling
        for i, player in enumerate(sorted_available[:num_picks]):
            # Check if player fits opponent needs (simplified)
            # For now, just use ADP
            predicted_picks.append(player)
        
        return predicted_picks
    
    def _optimize_category_targets(
        self,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState
    ) -> Dict[str, float]:
        """
        Determine which categories to target based on current standings.
        Uses ACTUAL STANDINGS POINTS (not just totals) to prioritize categories.
        Returns dict of category -> target priority (0-1).
        
        CRITICAL: Teams below 1000 IP get 1 point (worst) in ALL pitching categories.
        This makes IP accumulation the highest priority for pitching teams below minimum.
        """
        IP_MIN = 1000.0
        
        # Calculate ACTUAL STANDINGS with points (not just totals)
        # This gives us real-time standings context
        all_rosters_for_standings = {**all_team_rosters}
        if draft_state.my_team_name not in all_rosters_for_standings:
            all_rosters_for_standings[draft_state.my_team_name] = my_team
        
        standings = self.standings_calculator.calculate_standings(all_rosters_for_standings)
        category_points = standings.get('category_points', {})
        total_points = standings.get('total_points', {})
        my_team_name = draft_state.my_team_name
        my_total_points = total_points.get(my_team_name, 0)
        
        # Calculate current projected totals
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        my_ip = my_totals.get('IP', 0)
        below_ip_minimum = my_ip < IP_MIN
        
        # Get my current points in each category
        my_category_points = {}
        for category in self.standings_calculator.BATTING_CATEGORIES + self.standings_calculator.PITCHING_CATEGORIES:
            if category in category_points:
                my_category_points[category] = category_points[category].get(my_team_name, 0)
            else:
                my_category_points[category] = 0
        
        # Calculate opponent totals for comparison
        opponent_totals_list = []
        for team_name, roster in all_team_rosters.items():
            totals = self.standings_calculator._calculate_team_totals(roster)
            opponent_totals_list.append(totals)
        
        # Determine category priorities
        category_priorities = {}
        
        # Bob Uecker League categories
        batting_cats = ['HR', 'OBP', 'R', 'RBI', 'SB']
        pitching_cats = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']
        
        for category in batting_cats + pitching_cats:
            my_value = my_totals.get(category, 0)
            
            # IMPORTANT: If below IP minimum, pitching categories are less valuable
            # (we'll get 1 point = worst in all of them), but this shouldn't override
            # everything - we still need to balance with getting good players
            if category in pitching_cats and below_ip_minimum:
                # High priority but not maximum - encourage IP accumulation without
                # completely overriding value considerations
                # We'll handle IP needs separately in team needs analysis
                category_priorities[category] = 0.75  # High priority but not absolute
                continue
            
            # Compare to opponents
            opponent_values = [totals.get(category, 0) for totals in opponent_totals_list]
            if opponent_values:
                avg_opponent = sum(opponent_values) / len(opponent_values)
                median_opponent = sorted(opponent_values)[len(opponent_values) // 2]
                
                # Priority based on how far behind we are
                if category in ['ERA', 'WHIP']:  # Lower is better
                    if median_opponent == 0:
                        # No opponent data yet - use default priority
                        category_priorities[category] = 0.5
                    elif my_value > median_opponent:
                        # We're worse (higher ERA/WHIP) - high priority
                        # Lower ERA/WHIP = better = more points
                        category_priorities[category] = min(1.0, (my_value - median_opponent) / max(0.1, median_opponent))
                    else:
                        category_priorities[category] = 0.3  # We're good, low priority
                else:  # Higher is better
                    if median_opponent == 0:
                        # No opponent data yet - use default priority
                        category_priorities[category] = 0.5
                    elif my_value < median_opponent:
                        # We're behind - high priority
                        category_priorities[category] = min(1.0, (median_opponent - my_value) / max(1, median_opponent))
                    else:
                        category_priorities[category] = 0.3  # We're ahead, low priority
        
        return category_priorities
    
    def _optimize_category_targets_batched(
        self,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        all_team_totals: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Batched version of _optimize_category_targets that reuses pre-calculated totals.
        Faster for auto-draft when calculating many recommendations.
        """
        IP_MIN = 1000.0
        
        # Use batched totals (already calculated)
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        opponent_totals_list = [totals for team_name, totals in all_team_totals.items()]
        
        my_ip = my_totals.get('IP', 0)
        below_ip_minimum = my_ip < IP_MIN
        
        # Determine category priorities
        category_priorities = {}
        
        # Bob Uecker League categories
        batting_cats = ['HR', 'OBP', 'R', 'RBI', 'SB']
        pitching_cats = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']
        
        for category in batting_cats + pitching_cats:
            my_value = my_totals.get(category, 0)
            
            # IMPORTANT: If below IP minimum, pitching categories are less valuable
            # (we'll get 1 point = worst in all of them), but this shouldn't override
            # everything - we still need to balance with getting good players
            if category in pitching_cats and below_ip_minimum:
                # High priority but not maximum - encourage IP accumulation without
                # completely overriding value considerations
                # We'll handle IP needs separately in team needs analysis
                category_priorities[category] = 0.75  # High priority but not absolute
                continue
            
            # Compare to opponents
            opponent_values = [totals.get(category, 0) for totals in opponent_totals_list]
            if opponent_values:
                avg_opponent = sum(opponent_values) / len(opponent_values)
                median_opponent = sorted(opponent_values)[len(opponent_values) // 2]
                
                # Priority based on how far behind we are
                if category in ['ERA', 'WHIP']:  # Lower is better
                    if median_opponent == 0:
                        # No opponent data yet - use default priority
                        category_priorities[category] = 0.5
                    elif my_value > median_opponent:
                        # We're worse (higher ERA/WHIP) - high priority
                        # Lower ERA/WHIP = better = more points
                        category_priorities[category] = min(1.0, (my_value - median_opponent) / max(0.1, median_opponent))
                    else:
                        category_priorities[category] = 0.3  # We're good, low priority
                else:  # Higher is better
                    if median_opponent == 0:
                        # No opponent data yet - use default priority
                        category_priorities[category] = 0.5
                    elif my_value < median_opponent:
                        # We're behind - high priority
                        category_priorities[category] = min(1.0, (median_opponent - my_value) / max(1, median_opponent))
                    else:
                        category_priorities[category] = 0.3  # We're ahead, low priority
        
        return category_priorities
    
    def _calculate_category_target_score(
        self,
        player: Player,
        my_team: List[Player],
        category_priorities: Dict[str, float]
    ) -> float:
        """
        Calculate score based on how well player helps target categories.
        
        CRITICAL: For pitchers, lower ERA/WHIP = better = more points.
        Also accounts for IP minimum requirement.
        """
        score = 0.0
        
        # Check IP status for pitching categories
        IP_MIN = 1000.0
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        my_ip = my_totals.get('IP', 0)
        below_ip_minimum = my_ip < IP_MIN
        
        # Calculate player's category contributions
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        if is_pitcher:
            # CRITICAL: If below IP minimum, ALL pitching category contributions are meaningless
            # (we'll get 1 point = worst regardless). But we still want to accumulate IP,
            # so the IP contribution is handled in _analyze_team_needs, not here.
            # Here we focus on category improvements assuming we'll meet IP minimum.
            
            # Pitching categories
            if player.projected_strikeouts:
                score += player.projected_strikeouts * 0.1 * category_priorities.get('K', 0.5)
            
            # ERA: Lower is better (lower ERA = more points in standings)
            # So a pitcher with 3.00 ERA is better than one with 4.00 ERA
            if player.projected_era:
                # Lower ERA = better, so we reward lower ERA more
                # Scale: 2.00 ERA = best (100%), 5.00 ERA = worst (0%)
                era_contribution = max(0, (5.0 - player.projected_era) / 3.0)  # Normalized 0-1
                score += era_contribution * 50 * category_priorities.get('ERA', 0.5)
            
            # WHIP: Lower is better (lower WHIP = more points in standings)
            if player.projected_whip:
                # Lower WHIP = better, so we reward lower WHIP more
                # Scale: 0.90 WHIP = best (100%), 1.50 WHIP = worst (0%)
                whip_contribution = max(0, (1.50 - player.projected_whip) / 0.60)  # Normalized 0-1
                score += whip_contribution * 50 * category_priorities.get('WHIP', 0.5)
            
            if player.projected_wins:
                score += player.projected_wins * 2.0 * category_priorities.get('WQS', 0.5)
            if player.projected_quality_starts:
                score += player.projected_quality_starts * 2.0 * category_priorities.get('WQS', 0.5)
            if player.projected_saves:
                score += player.projected_saves * 3.0 * category_priorities.get('SHOLDS', 0.5)
            if player.projected_holds:
                # SHOLDS = Saves + (Holds * 0.5)
                score += (player.projected_holds * 0.5) * 1.5 * category_priorities.get('SHOLDS', 0.5)
        else:
            # Batting categories
            if player.projected_home_runs:
                score += player.projected_home_runs * 2.5 * category_priorities.get('HR', 0.5)
            if player.projected_runs:
                score += player.projected_runs * 0.6 * category_priorities.get('R', 0.5)
            if player.projected_rbi:
                score += player.projected_rbi * 0.6 * category_priorities.get('RBI', 0.5)
            if player.projected_stolen_bases:
                score += player.projected_stolen_bases * 3.5 * category_priorities.get('SB', 0.5)
            if player.projected_obp:
                obp_contribution = max(0, (player.projected_obp - 0.300) * 500)
                score += obp_contribution * category_priorities.get('OBP', 0.5)
        
        return score
    
    def _calculate_player_value(
        self,
        player: Player,
        my_team: List[Player],
        available_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]],
        use_ml: bool = True,
        team_name: Optional[str] = None,
        is_auto_draft: bool = False,
        all_team_totals: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Tuple[float, str]:
        """
        Calculate a value score for a player.
        
        Args:
            team_name: Optional team name. If None, uses draft_state.my_team_name
        
        Returns (score, reasoning)
        """
        if team_name is None:
            team_name = draft_state.my_team_name
        
        score = 0.0
        reasoning_parts = []
        
        # Determine if player is a pitcher (used multiple times)
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        # === CRITICAL: Check if we need pitchers URGENTLY (before ML prediction) ===
        pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        is_pitcher = player.position in ['SP', 'RP', 'P']
        current_round = draft_state.current_round
        
        # Calculate current IP
        current_ip = self._get_team_pitching_ip(my_team)
        IP_MIN = 1000.0
        below_ip_minimum = current_ip < IP_MIN
        
        urgent_pitcher_need = False
        pitcher_emergency_boost = 0.0
        
        if is_pitcher:
            # Let the ML model evaluate pitchers naturally - no artificial boosts/penalties
            # Only apply emergency boosts in truly critical situations (round 7+ with 0 pitchers)
            # The ML model should handle normal pitcher evaluation based on value
            
            # Priority 1: If we have 0 pitchers by round 7+, this is a real emergency
            # But keep the boost moderate - let ML model still have primary say
            if pitcher_count == 0 and current_round >= 7:
                # Round 7+ with 0 pitchers - moderate emergency boost
                pitcher_emergency_boost = 100.0  # Small boost to nudge, not override
                urgent_pitcher_need = True
                print(f"EMERGENCY: Round {current_round} with 0 pitchers - small boost for {player.name} (+{pitcher_emergency_boost})")
            
            # Priority 2: If below IP minimum in late rounds (round 10+), small boost
            # Don't worry about IP in early/mid rounds - ML model handles it
            if below_ip_minimum and current_round >= 10:
                ip_deficit = IP_MIN - current_ip
                # Calculate how much IP this pitcher adds
                pitcher_ip = player.projected_innings_pitched or 0
                if pitcher_ip is None or pitcher_ip == 0:
                    if player.projected_quality_starts:
                        pitcher_ip = player.projected_quality_starts * 6.5
                    elif player.projected_saves:
                        pitcher_ip = player.projected_saves * 1.0
                    elif player.position == 'SP':
                        pitcher_ip = 150.0
                    else:
                        pitcher_ip = 60.0
                
                # Small boost based on IP contribution (only in late rounds)
                ip_boost = min(pitcher_ip, ip_deficit) / IP_MIN * 50.0  # Small boost (max 50 points)
                pitcher_emergency_boost += ip_boost
                urgent_pitcher_need = True
                print(f"IP CONCERN (Round {current_round}): {current_ip:.0f}/{IP_MIN:.0f} IP - small boost for {player.name} (+{ip_boost:.0f})")
        
        # === 100% ML-BASED VALUE PREDICTION (disabled for auto-draft) ===
        # The ML model uses ALL features including contextual factors (team needs, position scarcity,
        # category targeting, comparative advantage, risk) - ALL baked into one AI decision
        # For auto-draft: Skip ML model for speed, use simplified rule-based scoring
        ml_value = None
        ml_score = 0.0
        if use_ml and not is_auto_draft:
            # Try to load ML models if not already loaded
            if not self._ml_models_loaded:
                self._ml_models_loaded = self.ml_trainer.load_models()
            
            if self._ml_models_loaded:
            try:
                pick_number = len(draft_state.picks) + 1
                    round_num = draft_state.current_round
                    # Pass recommendation_engine so ML can calculate ALL contextual factors
                    # Team needs, position scarcity, category targeting, comparative advantage, risk
                    # All baked into the ML model - 100% AI decision
                    ml_value = self.ml_trainer.predict_player_value(
                        player, my_team, available_players, pick_number, round_num, all_team_rosters,
                        recommendation_engine=self,
                        draft_state=draft_state,
                        team_name=team_name
                    )
                    # Scale ML prediction to match score range (ML predicts value, we need score)
                    # ML value is typically 0-100, scale to 0-1000 for scoring
                    ml_score = ml_value * 10
                    score = ml_score + pitcher_emergency_boost  # ML model + emergency pitcher boost
            except Exception as e:
                # Fall back to rule-based if ML fails
                    print(f"ML prediction failed for {player.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    ml_value = None
        
        # === FALLBACK: RULE-BASED SCORING (when ML not available OR for auto-draft) ===
        if ml_value is None:
            # Add emergency pitcher boost to rule-based scoring too
            score += pitcher_emergency_boost
            # For auto-draft: Use simplified scoring (ADP + team needs only, skip comparative advantage)
            # For user recommendations: Use full contextual factors
            if is_auto_draft:
                # SIMPLIFIED AUTO-DRAFT SCORING (faster)
                # 1. ADP value (primary)
                custom_adp_score, custom_adp_reasoning = self._analyze_custom_adp_value(
                    player, draft_state, available_players
                )
                score += custom_adp_score * 0.60  # 60% weight on ADP
                
                # 2. Team needs (secondary)
                needs_score, needs_reasoning = self._analyze_team_needs(
                    player, my_team, draft_state, available_players
                )
                score += needs_score * 0.30  # 30% weight on team needs
                
                # 3. Position scarcity (light weight)
        position_score, pos_reasoning = self._analyze_position_scarcity(
            player, my_team, available_players, draft_state, all_team_rosters
        )
                score += position_score * 0.10  # 10% weight on position scarcity
                
                # Skip: Category targeting, comparative advantage, risk (too expensive for auto-draft)
            else:
                # FULL RULE-BASED SCORING (for user recommendations)
                # Use ADP + contextual factors as fallback
                custom_adp_score, custom_adp_reasoning = self._analyze_custom_adp_value(
                    player, draft_state, available_players
                )
                score += custom_adp_score * 0.50  # 50% weight on ADP when ML not available
                
                contextual_score = 0.0
                # 1. Team needs analysis
        needs_score, needs_reasoning = self._analyze_team_needs(
            player, my_team, draft_state, available_players
        )
                contextual_score += needs_score * 0.30
                
                # 2. Position scarcity analysis
                position_score, pos_reasoning = self._analyze_position_scarcity(
                    player, my_team, available_players, draft_state, all_team_rosters
                )
                contextual_score += position_score * 0.25
                
                # 3. Category-specific optimization
                category_priorities = self._optimize_category_targets(my_team, all_team_rosters, draft_state)
                category_score = self._calculate_category_target_score(player, my_team, category_priorities)
                contextual_score += category_score * 0.20
                
                # 4. Comparative advantage
        relative_score, relative_reasoning = self._analyze_relative_advantage(
            player, my_team, all_team_rosters, draft_state, available_players, team_name
        )
                contextual_score += relative_score * 0.15
        
                # 5. Risk assessment
        risk_score, risk_reasoning = self._analyze_risk_factors(player)
                contextual_score += risk_score * 0.10
                
                score += contextual_score * 0.50  # 50% contextual when ML not available
        
        # Get reasoning components for display (even when using ML)
        custom_adp_score, custom_adp_reasoning = self._analyze_custom_adp_value(
            player, draft_state, available_players
        )
        needs_score, needs_reasoning = self._analyze_team_needs(
            player, my_team, draft_state, available_players
        )
        position_score, pos_reasoning = self._analyze_position_scarcity(
            player, my_team, available_players, draft_state, all_team_rosters
        )
        relative_score, relative_reasoning = self._analyze_relative_advantage(
            player, my_team, all_team_rosters, draft_state, available_players, team_name
        )
        risk_score, risk_reasoning = self._analyze_risk_factors(player)
        value_score, value_reasoning = self._analyze_projected_value(
            player, available_players
        )
        
        # Store for reasoning display
        if custom_adp_reasoning:
            reasoning_parts.append(custom_adp_reasoning)
        
        # Removed extra ADP penalty for pitchers - team needs analysis already handles pitcher value
        # The penalty was preventing pitchers from being recommended even when needed
        
        # Removed pitcher count penalty - team needs analysis already handles this properly
        # The _analyze_team_needs method already:
        # - Gives bonuses when pitchers are needed (< 9 pitchers)
        # - Gives bonuses when behind pace (should have more pitchers by this round)
        # - Gives bonuses for IP accumulation when below minimum
        # - Gives penalties when IP would exceed maximum
        # The extra penalty here was too aggressive and prevented pitchers from being recommended
        # even when team needs analysis said they were needed
        
        # ML value is already calculated above, no need to recalculate
        
        # ML value is already calculated above with all contextual factors baked in
        
        # Build comprehensive reasoning (concise paragraph format)
        reasoning = self._build_detailed_reasoning(
            player, my_team, all_team_rosters, draft_state, team_name,
            custom_adp_reasoning, pos_reasoning, needs_reasoning, 
            relative_reasoning, risk_reasoning, value_reasoning, ml_value
        )
        
        return score, reasoning
    
    def _build_detailed_reasoning(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        draft_state: DraftState,
        team_name: str,
        custom_adp_reasoning: str,
        pos_reasoning: str,
        needs_reasoning: str,
        relative_reasoning: str,
        risk_reasoning: str,
        value_reasoning: str,
        ml_value: Optional[float] = None
    ) -> str:
        """
        Build concise paragraph reasoning for why this player is recommended.
        Incorporates ML model insights when available.
        """
        sentences = []
        
        # Start with ML model insight if available (ALL contextual factors baked into AI)
        if ml_value is not None and ml_value > 0:
            if ml_value > 50:
                sentences.append(f"Our AI model (analyzing 44+ features including team needs, position scarcity, category targeting, comparative advantage, and risk factors) rates {player.name} as an elite value pick for your specific draft situation,")
            elif ml_value > 25:
                sentences.append(f"Our AI model (analyzing 44+ features including team needs, position scarcity, category targeting, comparative advantage, and risk factors) indicates {player.name} offers strong value for your specific draft situation,")
        else:
                sentences.append(f"Our AI model (analyzing 44+ features including team needs, position scarcity, category targeting, comparative advantage, and risk factors) suggests {player.name} is a solid pick for your specific draft situation,")
        elif ml_value is None:
            # ML model not available - mention it's rule-based
            sentences.append(f"Based on rule-based analysis (ML model not available), {player.name} appears to be a good fit,")
        
        # ADP context
        if custom_adp_reasoning:
            if "excellent value" in custom_adp_reasoning.lower() or "good value" in custom_adp_reasoning.lower():
                adp_info = custom_adp_reasoning.split(" - ")[-1] if " - " in custom_adp_reasoning else custom_adp_reasoning
                if not sentences:
                    sentences.append(f"{player.name} is available at {adp_info.lower()},")
        else:
                    sentences.append(f"and he's available at {adp_info.lower()}.")
            elif "at value" in custom_adp_reasoning.lower():
                adp_info = custom_adp_reasoning.split(" - ")[-1] if " - " in custom_adp_reasoning else custom_adp_reasoning
                if not sentences:
                    sentences.append(f"{player.name} is being drafted {adp_info.lower()},")
                else:
                    sentences.append(f"he's being drafted {adp_info.lower()}.")
            elif "too early" not in custom_adp_reasoning.lower():
                adp_info = custom_adp_reasoning.split(" - ")[-1] if " - " in custom_adp_reasoning else custom_adp_reasoning
                if not sentences:
                    sentences.append(f"{player.name} has {adp_info.lower()},")
                else:
                    sentences.append(f"with {adp_info.lower()}.")
        
        # Position and team needs (most important context)
        if needs_reasoning:
            # Extract key info from needs reasoning
            needs_parts = needs_reasoning.split(" | ")
            key_needs = []
            for part in needs_parts[:2]:  # Take first 2 needs
                if "Fills" in part or "Need" in part or "Building" in part:
                    # Clean up the text
                    clean_part = part.replace("Fills ", "").replace("Need ", "").replace("Building ", "")
                    key_needs.append(clean_part.lower())
            if key_needs:
                if not sentences:
                    sentences.append(f"{player.name} " + " and ".join(key_needs) + ".")
            else:
                    sentences.append(" ".join(key_needs) + ".")
        
        # Category contributions (if significant)
        category_analysis = self._analyze_category_needs_detailed(player, my_team, all_team_rosters, team_name)
        if category_analysis:
            # Extract top 1-2 category improvements
            category_parts = category_analysis.split(" | ")
            top_categories = category_parts[:2]  # Top 2 categories
            if top_categories:
                cat_summary = ", ".join([c.split(":")[0] if ":" in c else c for c in top_categories]).lower()
                sentences.append(f"He helps with {cat_summary}.")
        
        # Risk assessment (only if significant)
        if risk_reasoning and ("high risk" in risk_reasoning.lower() or "injured" in risk_reasoning.lower()):
            sentences.append(f"Note: {risk_reasoning.lower()}.")
        
        # Position scarcity (only if relevant - not "deep pool")
        if pos_reasoning and "deep pool" not in pos_reasoning.lower() and "scarce" in pos_reasoning.lower():
            pos_summary = pos_reasoning.split(":")[-1].strip() if ":" in pos_reasoning else pos_reasoning
            sentences.append(f"Position context: {pos_summary.lower()}.")
        
        # Build final paragraph
        if sentences:
            reasoning = " ".join(sentences)
            # Capitalize first letter
            reasoning = reasoning[0].upper() + reasoning[1:] if len(reasoning) > 1 else reasoning
            return reasoning
        else:
            return f"{player.name} represents good value based on current draft state and team needs."
    
    def _analyze_category_needs_detailed(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        team_name: str
    ) -> str:
        """Provide detailed analysis of which categories this player helps with."""
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        projected_roster = my_team + [player]
        projected_totals = self.standings_calculator._calculate_team_totals(projected_roster)
        
        category_improvements = []
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        if is_pitcher:
            # Pitching categories
            if player.projected_strikeouts:
                k_improvement = projected_totals['K'] - my_totals['K']
                if k_improvement > 0:
                    category_improvements.append(f"Strikeouts: +{k_improvement:.0f} (need to increase K count)")
            
            if player.projected_wins or player.projected_quality_starts:
                wqs_improvement = (projected_totals['W'] + projected_totals['QS']) - (my_totals['W'] + my_totals['QS'])
                if wqs_improvement > 0:
                    category_improvements.append(f"Wins+QS: +{wqs_improvement:.1f}")
            
            if player.projected_saves or player.projected_holds:
                sholds_improvement = projected_totals['SV'] + (projected_totals['HD'] * 0.5) - (my_totals['SV'] + (my_totals['HD'] * 0.5))
                if sholds_improvement > 0:
                    category_improvements.append(f"Saves+Holds: +{sholds_improvement:.1f}")
            
            if player.projected_era:
                era_improvement = my_totals['ERA'] - projected_totals['ERA']  # Lower is better
                if era_improvement > 0:
                    category_improvements.append(f"ERA: Improves by {era_improvement:.2f} (lower is better)")
            
            if player.projected_whip:
                whip_improvement = my_totals['WHIP'] - projected_totals['WHIP']  # Lower is better
                if whip_improvement > 0:
                    category_improvements.append(f"WHIP: Improves by {whip_improvement:.3f} (lower is better)")
        else:
            # Batting categories
            if player.projected_home_runs:
                hr_improvement = projected_totals['HR'] - my_totals['HR']
                if hr_improvement > 0:
                    category_improvements.append(f"Home Runs: +{hr_improvement:.0f} (need to increase HR count)")
            
            if player.projected_runs:
                r_improvement = projected_totals['R'] - my_totals['R']
                if r_improvement > 0:
                    category_improvements.append(f"Runs: +{r_improvement:.0f}")
            
            if player.projected_rbi:
                rbi_improvement = projected_totals['RBI'] - my_totals['RBI']
                if rbi_improvement > 0:
                    category_improvements.append(f"RBI: +{rbi_improvement:.0f}")
            
            if player.projected_stolen_bases:
                sb_improvement = projected_totals['SB'] - my_totals['SB']
                if sb_improvement > 0:
                    category_improvements.append(f"Stolen Bases: +{sb_improvement:.0f} (need to increase SB count)")
            
            if player.projected_obp:
                obp_improvement = projected_totals['OBP'] - my_totals['OBP']
                if obp_improvement > 0:
                    category_improvements.append(f"OBP: +{obp_improvement:.3f} (need to increase OBP)")
        
        if category_improvements:
            return " | ".join(category_improvements)
        else:
            return "Provides balanced contributions across multiple categories"
    
    def _get_comparative_advantage_details(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        team_name: str
    ) -> str:
        """Get detailed comparative advantage analysis."""
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        projected_roster = my_team + [player]
        projected_totals = self.standings_calculator._calculate_team_totals(projected_roster)
        
        advantages = []
        
        # Check each category
        for category in ['HR', 'R', 'RBI', 'SB', 'W', 'K', 'SV', 'HD']:
            my_value = my_totals[category]
            projected_value = projected_totals[category]
            improvement = projected_value - my_value
            
            if improvement > 0:
                # Count opponents ahead of us
                opponents_ahead = sum(
                    1 for other_team_name, roster in all_team_rosters.items()
                    if other_team_name != team_name
                    for opp_totals in [self.standings_calculator._calculate_team_totals(roster)]
                    if opp_totals[category] > my_value
                )
                
                if opponents_ahead > 0:
                    advantages.append(f"This player helps us catch up in {category} (+{improvement:.1f}), passing {opponents_ahead} opponent(s)")
        
        # Check position strategy
        my_hitters = sum(1 for p in my_team if p.position not in ['SP', 'RP', 'P'])
        my_pitchers = len(my_team) - my_hitters
        
        avg_opponent_hitters = np.mean([
            sum(1 for p in roster if p.position not in ['SP', 'RP', 'P'])
            for roster in all_team_rosters.values()
        ]) if all_team_rosters else 0
        
        is_hitter = player.position not in ['SP', 'RP', 'P']
        if is_hitter and my_hitters < avg_opponent_hitters:
            advantages.append(f"Opponents are stacking hitters ({avg_opponent_hitters:.1f} avg), we need to balance with {my_hitters} hitters")
        elif not is_hitter and my_pitchers < 9:
            advantages.append(f"Building pitching depth ({my_pitchers}/9 pitchers) to gain advantage")
        
        if advantages:
            return " | ".join(advantages)
        else:
            return "Provides solid value relative to opponents"
    
    def _analyze_custom_adp_value(
        self,
        player: Player,
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        Analyze custom ADP value (league-specific ADP from player dict).
        This is the PRIMARY signal (50% weight) - heavily penalize high custom ADP players.
        """
        current_pick = len(draft_state.picks) + 1
        
        # Use custom ADP if available (from player dict), fall back to regular ADP
        # Custom ADP is stored in the adp field if it was calculated
        player_adp = player.adp  # This should be custom ADP if calculated
        
        if player_adp is None:
            # No ADP - significant penalty for custom ADP (it's the primary signal)
            return -100, "No custom ADP data"
        
        # Calculate ADP difference (how far off are we?)
        adp_difference = current_pick - player_adp
        
        # If we're picking way before their ADP, that's good (negative difference = good)
        # If we're picking way after their ADP, that's bad (positive difference = bad)
        
        # Early picks (1-50): Strong ADP enforcement
        if current_pick <= 50:
            if player_adp > current_pick + 15:
                # Way too early for this player
                penalty = -500 - ((player_adp - current_pick) * 10)
                return penalty, f"Custom ADP {player_adp:.1f} - WAY TOO EARLY (pick {current_pick})"
            elif player_adp > current_pick + 8:
                # Too early - strong penalty
                penalty = -200 - ((player_adp - current_pick) * 8)
                return penalty, f"Custom ADP {player_adp:.1f} - too early (pick {current_pick})"
            elif player_adp > current_pick + 5:
                # Slightly early - moderate penalty
                penalty = -80 - ((player_adp - current_pick) * 6)
                return penalty, f"Custom ADP {player_adp:.1f} - slightly early (pick {current_pick})"
            elif player_adp < current_pick - 10:
                # Great value - picking someone who should have gone earlier
                bonus = 100 + ((current_pick - player_adp) * 3)
                return bonus, f"Custom ADP {player_adp:.1f} - excellent value!"
            elif player_adp <= current_pick + 5 and player_adp >= current_pick - 8:
                # Reasonable range (±5 ahead, -8 behind)
                return 0, f"Custom ADP {player_adp:.1f} - at value"
            else:
                # Outside reasonable range
                return -30, f"Custom ADP {player_adp:.1f} - outside optimal range"
        
        # Mid picks (51-150): Moderate penalties
        elif current_pick <= 150:
            if player_adp > current_pick + 25:
                penalty = -300 - ((player_adp - current_pick) * 5)
                return penalty, f"Custom ADP {player_adp:.1f} - too early (pick {current_pick})"
            elif player_adp < current_pick - 15:
                bonus = 80 + ((current_pick - player_adp) * 2)
                return bonus, f"Custom ADP {player_adp:.1f} - good value!"
            elif player_adp <= current_pick + 10 and player_adp >= current_pick - 10:
                return 0, f"Custom ADP {player_adp:.1f} - reasonable"
            else:
                return -20, f"Custom ADP {player_adp:.1f} - outside range"
        
        # Late picks (151+): Lighter penalties, more flexibility
        else:
            if player_adp > current_pick + 40:
                penalty = -100 - ((player_adp - current_pick) * 2)
                return penalty, f"Custom ADP {player_adp:.1f} - early (pick {current_pick})"
            elif player_adp < current_pick - 20:
                bonus = 50 + ((current_pick - player_adp) * 1)
                return bonus, f"Custom ADP {player_adp:.1f} - value pick"
            else:
                return 0, f"Custom ADP {player_adp:.1f} - acceptable"
    
    def _analyze_risk_factors(self, player: Player) -> Tuple[float, str]:
        """
        Analyze risk factors: injury risk, age decline, sample size confidence.
        Returns (score, reasoning) where negative score = higher risk.
        """
        risk_score = 0.0
        risk_factors = []
        
        # Injury risk (0-1, higher = more risk)
        if player.injury_risk_score:
            if player.injury_risk_score > 0.7:
                risk_score -= 50
                risk_factors.append("high injury risk")
            elif player.injury_risk_score > 0.4:
                risk_score -= 25
                risk_factors.append("moderate injury risk")
        
        # Current injury
        if player.current_injury:
            risk_score -= 75
            risk_factors.append(f"currently injured: {player.current_injury}")
        
        # Sample size confidence (0-1, lower = less confidence/prospect)
        if player.sample_size_confidence:
            if player.sample_size_confidence < 0.4:
                risk_score -= 30
                risk_factors.append("low sample size (prospect)")
            elif player.sample_size_confidence < 0.6:
                risk_score -= 15
                risk_factors.append("limited sample size")
        
        # Age decline
        if player.age_decline_factor:
            if player.age_decline_factor < 0.85:
                risk_score -= 20
                risk_factors.append("age-related decline")
            elif player.age_decline_factor < 0.95:
                risk_score -= 10
                risk_factors.append("slight age decline")
        
        # Positive factors
        if player.contract_year:
            risk_score += 10
            risk_factors.append("contract year (motivation)")
        
        if player.sample_size_confidence and player.sample_size_confidence > 0.8:
            risk_score += 10
            risk_factors.append("proven track record")
        
        reasoning = ", ".join(risk_factors) if risk_factors else "low risk"
        return risk_score, reasoning
    
    def _analyze_adp_value(
        self,
        player: Player,
        draft_state: DraftState,
        available_players: List[Player]
    ) -> Tuple[float, str]:
        """
        DEPRECATED: Use _analyze_custom_adp_value instead.
        Kept for backward compatibility.
        """
        return self._analyze_custom_adp_value(player, draft_state, available_players)
        
        if player_adp is None:
            # No ADP - slight penalty, but not huge
            return -20, "No ADP data"
        
        # Calculate ADP difference (how far off are we?)
        adp_difference = current_pick - player_adp
        
        # If we're picking way before their ADP, that's good (negative difference = good)
        # If we're picking way after their ADP, that's bad (positive difference = bad)
        
        # Early picks (1-50): Moderate ADP enforcement - stay reasonably close to ADP
        if current_pick <= 50:
            if player_adp > current_pick + 15:
                # Way too early for this player
                penalty = -400 - ((player_adp - current_pick) * 8)
                return penalty, f"ADP {player_adp} - WAY TOO EARLY (pick {current_pick})"
            elif player_adp > current_pick + 8:
                # Too early - moderate penalty
                penalty = -150 - ((player_adp - current_pick) * 5)
                return penalty, f"ADP {player_adp} - too early (pick {current_pick})"
            elif player_adp > current_pick + 5:
                # Slightly early - light penalty
                penalty = -50 - ((player_adp - current_pick) * 5)
                return penalty, f"ADP {player_adp} - slightly early (pick {current_pick})"
            elif player_adp < current_pick - 10:
                # Great value - picking someone who should have gone earlier
                bonus = 50 + ((current_pick - player_adp) * 2)
                return bonus, f"ADP {player_adp} - great value!"
            elif player_adp <= current_pick + 5 and player_adp >= current_pick - 8:
                # Reasonable range (±5 ahead, -8 behind)
                return 0, f"ADP {player_adp} - at value"
            else:
                # Outside reasonable range
                return -20, f"ADP {player_adp} - outside optimal range"
        
        # Mid picks (51-150): Moderate penalties - stay reasonably close to ADP
        elif current_pick <= 150:
            if player_adp > current_pick + 20:
                penalty = -250 - ((player_adp - current_pick) * 5)
                return penalty, f"ADP {player_adp} - too early (pick {current_pick})"
            elif player_adp > current_pick + 10:
                penalty = -100 - ((player_adp - current_pick) * 4)
                return penalty, f"ADP {player_adp} - early (pick {current_pick})"
            elif player_adp > current_pick + 5:
                penalty = -40 - ((player_adp - current_pick) * 3)
                return penalty, f"ADP {player_adp} - slightly early (pick {current_pick})"
            elif player_adp < current_pick - 20:
                bonus = 30 + ((current_pick - player_adp) * 1.5)
                return bonus, f"ADP {player_adp} - good value"
            elif player_adp <= current_pick + 5 and player_adp >= current_pick - 10:
                return 0, f"ADP {player_adp} - at value"
            else:
                return -20, f"ADP {player_adp} - outside optimal range"
        
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
        available_players: List[Player],
        team_name: Optional[str] = None
    ) -> Tuple[float, str]:
        """
        Analyze how much this player helps you vs. opponents.
        Uses ACTUAL STANDINGS POINTS to evaluate comparative advantage.
        Considers opponent strategies and adapts recommendations.
        """
        if team_name is None:
            team_name = draft_state.my_team_name
        
        score = 0.0
        reasoning_parts = []
        
        # Calculate ACTUAL STANDINGS with points (not just totals)
        # This gives us real-time standings context
        all_rosters_for_standings = {**all_team_rosters}
        if team_name not in all_rosters_for_standings:
            all_rosters_for_standings[team_name] = my_team
        
        # Current standings
        current_standings = self.standings_calculator.calculate_standings(all_rosters_for_standings)
        current_category_points = current_standings.get('category_points', {})
        current_total_points = current_standings.get('total_points', {})
        my_current_points = current_total_points.get(team_name, 0)
        
        # Calculate my current category totals
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        
        # Calculate projected totals if I draft this player
        my_projected_roster = my_team + [player]
        my_projected_totals = self.standings_calculator._calculate_team_totals(my_projected_roster)
        
        # Calculate projected standings with this player
        all_rosters_projected = {**all_team_rosters}
        all_rosters_projected[team_name] = my_projected_roster
        projected_standings = self.standings_calculator.calculate_standings(all_rosters_projected)
        projected_category_points = projected_standings.get('category_points', {})
        projected_total_points = projected_standings.get('total_points', {})
        my_projected_points = projected_total_points.get(team_name, 0)
        
        # Calculate points improvement
        points_improvement = my_projected_points - my_current_points
        if points_improvement > 0:
            # Boost score based on total points improvement
            score += points_improvement * 50  # Each point improvement is worth 50 score points
            reasoning_parts.append(f"+{points_improvement:.1f} total points")
        
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
        
        # Calculate opponent category totals and strategies (improved modeling)
        opponent_totals = {}
        opponent_strategies = {}  # Track if opponents are going heavy hitter/pitcher
        opponent_category_strengths = {}  # Track what categories opponents are strong in
        
        for other_team_name, roster in all_team_rosters.items():
            if other_team_name == team_name:
                continue
            totals = self.standings_calculator._calculate_team_totals(roster)
            opponent_totals[other_team_name] = totals
            
            # Analyze opponent strategy
            opponent_hitters = sum(1 for p in roster if p.position not in ['SP', 'RP', 'P'])
            opponent_pitchers = len(roster) - opponent_hitters
            opponent_strategies[other_team_name] = {
                'hitters': opponent_hitters,
                'pitchers': opponent_pitchers,
                'ratio': opponent_hitters / max(1, opponent_pitchers)
            }
            
            # Identify opponent category strengths
            category_strengths = {}
            for category in ['HR', 'R', 'RBI', 'SB', 'OBP', 'K', 'WQS', 'SHOLDS']:
                if category in totals:
                    category_strengths[category] = totals[category]
            opponent_category_strengths[other_team_name] = category_strengths
        
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
        # If opponents are going heavy hitters, pitchers become more valuable (but very conservatively)
        elif avg_opponent_hitter_ratio > 1.5 and is_pitcher:
            my_pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
            # Only give bonus if we actually need pitchers (have fewer than 5)
            if my_pitcher_count < 5:
                score += 15  # Further reduced from 20
                reasoning_parts.append(f"Opponents heavy on hitters - pitchers valuable")
            else:
                score -= 20  # Penalty if we already have enough pitchers
                reasoning_parts.append("Have enough pitchers despite opponent strategy")
        
        # Early draft: Very conservative about pitcher runs
        current_pick = len(draft_state.picks) + 1
        my_pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        if is_pitcher and current_pick <= 100 and my_pitcher_count < 4:  # Only if we have < 4
            if total_pitchers_drafted > 60:  # Even higher threshold
                score += 15  # Reduced from 20
                reasoning_parts.append(f"Pitcher run happening ({total_pitchers_drafted} drafted) - consider value")
            # Remove the "undervalued" bonus - don't encourage early pitcher picks
        
        # Blocking value - prevent opponents from getting this player
        # Check which opponents need this position
        position_needed_by_opponents = 0
        critical_opponents = []
        
        for other_team_name, roster in all_team_rosters.items():
            if other_team_name == team_name:
                continue
            
            # Count how many players opponent has at this position
            opponent_count = sum(1 for p in roster if p.position == player.position)
            my_count = sum(1 for p in my_team if p.position == player.position)
            
            # Check if opponent needs this position more than I do
            position_requirements = {'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'OF': 4, 'P': 9}
            required = position_requirements.get(player.position, 1)
            
            if opponent_count < required and opponent_count < my_count:
                position_needed_by_opponents += 1
                critical_opponents.append(other_team_name)
        
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
            # Pitchers: Very conservative scarcity scoring
            # Pitchers are deep, so scarcity is less important
            if drafted_at_position > 70:  # Very many pitchers already taken
                scarcity_score = 50  # Further reduced from 70
                reasoning = f"Pitcher scarcity: {drafted_at_position} drafted, {available_at_position} left"
            elif drafted_at_position > 50:
                scarcity_score = 35  # Further reduced from 50
                reasoning = f"Pitcher: {drafted_at_position} drafted, {available_at_position} left"
            elif scarcity_ratio < 0.8:  # Only if truly scarce
                scarcity_score = 25  # Further reduced from 40
                reasoning = f"Pitcher: {available_at_position} left for {slots_remaining} slots"
            else:
                scarcity_score = 15  # Further reduced from 25
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
    
    def _get_team_pitching_ip(self, roster: List[Player]) -> float:
        """Calculate total projected innings pitched for a roster."""
        total_ip = 0.0
        pitchers = [p for p in roster if p.position in ['SP', 'RP', 'P']]
        
        for pitcher in pitchers:
            pitcher_ip = pitcher.projected_innings_pitched
            if pitcher_ip is None:
                # Estimate from QS
                if pitcher.projected_quality_starts:
                    pitcher_ip = pitcher.projected_quality_starts * 6.5
                elif pitcher.projected_saves:
                    pitcher_ip = pitcher.projected_saves * 1.0
                elif hasattr(pitcher, 'br_innings_pitched') and pitcher.br_innings_pitched:
                    pitcher_ip = pitcher.br_innings_pitched
                else:
                    if pitcher.position == 'SP':
                        pitcher_ip = 150.0
                    else:
                        pitcher_ip = 60.0
            total_ip += pitcher_ip or 0
        
        return total_ip
    
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
        Includes IP minimum/maximum considerations.
        """
        # Bob Uecker League position requirements:
        # 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P, 1 BENCH
        position_requirements = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
            'MI': 1,  # Middle Infielder (2B or SS)
            'CI': 1,  # Corner Infielder (1B or 3B)
            'OF': 4, 'U': 1,  # Utility (any offensive position)
            'SP': 9, 'RP': 9, 'P': 9,  # Any combination of pitchers
            'BENCH': 1  # Bench/Reserve (any player)
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
        current_round = draft_state.current_round
        
        # Calculate ideal hitter/pitcher balance
        hitters_needed = total_hitters_needed - hitter_count
        pitchers_needed = total_pitchers_needed - pitcher_count
        
        # CRITICAL: Ensure pitchers are drafted throughout the draft, not just at the end
        # Aim to have at least 1 pitcher by round 4, 2-3 by round 7, etc.
        ideal_pitcher_pace = [
            (4, 1),   # By round 4, should have 1 pitcher
            (7, 3),   # By round 7, should have 3 pitchers
            (10, 5),  # By round 10, should have 5 pitchers
            (15, 7),  # By round 15, should have 7 pitchers
        ]
        
        # Check if we're behind pace on pitchers
        behind_pace = False
        for target_round, target_pitchers in ideal_pitcher_pace:
            if current_round >= target_round and pitcher_count < target_pitchers:
                behind_pace = True
                break
        
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
            # Check IP minimum/maximum requirements
            current_ip = self._get_team_pitching_ip(my_team)
            IP_MIN = 1000.0
            IP_MAX = 1400.0
            
            # Estimate this pitcher's IP
            pitcher_ip = player.projected_innings_pitched
            if pitcher_ip is None:
                if player.projected_quality_starts:
                    pitcher_ip = player.projected_quality_starts * 6.5
                elif player.projected_saves:
                    pitcher_ip = player.projected_saves * 1.0
                elif hasattr(player, 'br_innings_pitched') and player.br_innings_pitched:
                    pitcher_ip = player.br_innings_pitched
                else:
                    if player.position == 'SP':
                        pitcher_ip = 150.0
                    else:
                        pitcher_ip = 60.0
            
            projected_total_ip = current_ip + (pitcher_ip or 0)
            
            # IP-based scoring
            # IMPORTANT: IP accumulation is a consideration, not the only factor
            if current_ip < IP_MIN:
                # Below minimum - need IP (but balanced with value)
                ip_deficit = IP_MIN - current_ip
                if ip_deficit > 0:
                    # Moderate bonus for helping reach minimum (not overriding value)
                    ip_contribution = min(pitcher_ip or 0, ip_deficit)
                    need_score += (ip_contribution / IP_MIN) * 80  # Moderate bonus (was 150)
                    reasoning_parts.append(f"Need IP to reach minimum ({current_ip:.0f}/{IP_MIN:.0f})")
            elif projected_total_ip > IP_MAX:
                # Would exceed maximum - penalty
                excess = projected_total_ip - IP_MAX
                penalty = min(200, excess * 2)  # Penalty based on excess
                need_score -= penalty
                reasoning_parts.append(f"Would exceed IP max ({projected_total_ip:.0f} > {IP_MAX:.0f})")
            elif current_ip < IP_MAX * 0.9:
                # In good range but not at max yet
            if pitchers_needed > 0:
                    need_score += pitchers_needed * 10
                    reasoning_parts.append(f"Building IP depth ({current_ip:.0f} IP)")
            
            # CRITICAL: Ensure pitchers are drafted throughout draft, not just at the end
            if behind_pace and pitcher_count == 0:
                # Very behind pace - no pitchers yet but should have some
                need_score += 60  # Strong bonus to get first pitcher
                reasoning_parts.append(f"Behind pace - should have pitcher by round {current_round}")
            elif behind_pace:
                # Behind pace but have some pitchers
                need_score += 40  # Moderate bonus
                reasoning_parts.append(f"Behind pace on pitchers ({pitcher_count} by round {current_round})")
            
            # Also consider pitcher count
            if pitchers_needed > 0:
                # Need pitchers - bonus based on need and pace
                base_bonus = pitchers_needed * 15  # Increased from 10
                need_score += base_bonus
                if pitchers_needed > my_picks_remaining / 2:
                    need_score += 30  # Urgent need
                    reasoning_parts.append(f"URGENT: Need {pitchers_needed} more pitchers")
                elif pitchers_needed > 4:
                    need_score += 20  # Moderate urgency
                    reasoning_parts.append(f"Need {pitchers_needed} more pitchers")
                elif current_round <= 10 and pitcher_count < 3:
                    # Early draft - encourage pitcher picks to build IP early
                    need_score += 25
                    reasoning_parts.append(f"Early draft - building pitcher depth")
            else:
                # Have enough pitchers, but check if we need IP
                if current_ip < IP_MIN:
                    # Still need IP even if we have enough pitchers
                    pass  # Already handled above
                else:
                    need_score -= 100  # Don't need more pitchers
                reasoning_parts.append("Have enough pitchers")
        
        # Early draft: Encourage getting first pitcher in rounds 2-4 if good value
        current_pick = len(draft_state.picks) + 1
        if current_pick <= 100:
            # Rounds 2-4 (picks ~14-52): Encourage first pitcher if reasonably near ADP
            if is_pitcher and pitcher_count == 0:
                if current_pick >= 14 and current_pick <= 52:
                    # Check if pitcher is at or reasonably near ADP
                    if player.adp:
                        adp_diff = player.adp - current_pick
                        if adp_diff <= 5 and adp_diff >= -5:  # Within 5 picks of ADP
                            need_score += 25  # Bonus for good value first pitcher
                            reasoning_parts.append(f"First pitcher - good value (ADP {player.adp})")
                        elif adp_diff > 5 and adp_diff <= 8:
                            need_score += 10  # Small bonus if slightly early
                            reasoning_parts.append(f"First pitcher - slightly early (ADP {player.adp})")
                elif current_pick > 52 and current_pick <= 80:
                    # Mid-draft: moderate bonus for first pitcher
                    need_score += 20
                    reasoning_parts.append("No pitchers yet - consider drafting")
                elif current_pick > 80:
                    # Late: stronger bonus
                    need_score += 30
                    reasoning_parts.append("No pitchers yet - consider drafting")
        
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

