"""Feature engineering for ML training using real-world data."""
import numpy as np
from typing import List, Dict, Optional
from src.models.player import Player
from src.models.draft import DraftState
from src.services.standings_calculator import StandingsCalculator


class FeatureEngineer:
    """Engineers features from player data for ML training."""
    
    def __init__(self):
        self.standings_calculator = StandingsCalculator()
    
    def extract_features_for_pick(
        self,
        player: Player,
        my_team: List[Player],
        all_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]],
        league_thresholds: Optional[Dict[str, float]] = None,
        my_team_name: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Extract comprehensive features for a draft pick.
        
        Args:
            player: Player being evaluated
            my_team: Current roster
            all_players: All available players
            draft_state: Current draft state
            all_team_rosters: All team rosters
            league_thresholds: Stats needed to win each category
            my_team_name: Name of my team (for excluding from opponent comparisons)
        
        Returns:
            Dictionary of feature names and values
        """
        features = {}
        current_pick = len(draft_state.picks) + 1
        round_num = draft_state.current_round
        is_pitcher = player.position in ['SP', 'RP', 'P']
        is_hitter = not is_pitcher
        
        # === 1. Player Statistical Features ===
        features.update(self._extract_player_stats(player, is_pitcher))
        
        # === 2. Projection Features (Multiple Systems) ===
        features.update(self._extract_projection_features(player, is_pitcher))
        
        # === 3. Advanced Metrics ===
        features.update(self._extract_advanced_metrics(player, is_pitcher))
        
        # === 4. Statcast/Statcast Features ===
        features.update(self._extract_statcast_features(player, is_pitcher))
        
        # === 5. Risk Features ===
        features.update(self._extract_risk_features(player))
        
        # === 6. Context Features ===
        features.update(self._extract_context_features(player, current_pick, round_num))
        
        # === 7. Team State Features ===
        features.update(self._extract_team_state_features(my_team, is_pitcher))
        
        # === 8. Position Scarcity Features ===
        features.update(self._extract_position_scarcity(
            player, all_players, draft_state, all_team_rosters
        ))
        
        # === 9. Comparative Advantage Features ===
        features.update(self._extract_comparative_advantage(
            player, my_team, all_team_rosters, league_thresholds, my_team_name
        ))
        
        # === 10. ADP Features (Dynamic Weighting) ===
        features.update(self._extract_adp_features(player, current_pick))
        
        return features
    
    def _extract_player_stats(self, player: Player, is_pitcher: bool) -> Dict[str, float]:
        """Extract historical statistical features."""
        features = {}
        
        if is_pitcher:
            features['br_wins'] = player.br_wins or 0
            features['br_saves'] = player.br_saves or 0
            features['br_innings_pitched'] = player.br_innings_pitched or 0
            features['br_earned_runs'] = player.br_earned_runs or 0
            features['br_cy_youngs'] = player.br_cy_youngs or 0
        else:
            features['br_runs'] = player.br_runs or 0
            features['br_rbi'] = player.br_rbi or 0
            features['br_home_runs'] = player.br_home_runs or 0
            features['br_stolen_bases'] = player.br_stolen_bases or 0
            features['br_hits'] = player.br_hits or 0
            features['br_mvps'] = player.br_mvps or 0
            features['br_all_stars'] = player.br_all_stars or 0
            features['br_gold_gloves'] = player.br_gold_gloves or 0
        
        return features
    
    def _extract_projection_features(self, player: Player, is_pitcher: bool) -> Dict[str, float]:
        """Extract features from multiple projection systems."""
        features = {}
        
        if is_pitcher:
            # Average projections across systems
            proj_w = [p for p in [
                player.projected_wins,
                player.br_proj_w,
                player.fg_steamer_w,
                player.fg_zips_w,
                player.fg_atc_w
            ] if p is not None]
            proj_k = [p for p in [
                player.projected_strikeouts,
                player.br_proj_k,
                player.fg_steamer_k,
                player.fg_zips_k,
                player.fg_atc_k
            ] if p is not None]
            proj_era = [p for p in [
                player.projected_era,
                player.br_proj_era,
                player.fg_steamer_era,
                player.fg_zips_era,
                player.fg_atc_era
            ] if p is not None]
            proj_whip = [p for p in [
                player.projected_whip,
                player.br_proj_whip,
                player.fg_steamer_whip,
                player.fg_zips_whip,
                player.fg_atc_whip
            ] if p is not None]
            
            features['avg_proj_w'] = np.mean(proj_w) if proj_w else 0
            features['avg_proj_k'] = np.mean(proj_k) if proj_k else 0
            features['avg_proj_era'] = np.mean(proj_era) if proj_era else 5.0
            features['avg_proj_whip'] = np.mean(proj_whip) if proj_whip else 1.5
            features['proj_std_w'] = np.std(proj_w) if len(proj_w) > 1 else 0
            features['proj_std_era'] = np.std(proj_era) if len(proj_era) > 1 else 0
        else:
            proj_hr = [p for p in [
                player.projected_home_runs,
                player.br_proj_hr,
                player.fg_steamer_hr,
                player.fg_zips_hr,
                player.fg_thebat_hr,
                player.fg_atc_hr
            ] if p is not None]
            proj_r = [p for p in [
                player.projected_runs,
                player.br_proj_r,
                player.fg_steamer_r,
                player.fg_zips_r,
                player.fg_atc_r
            ] if p is not None]
            proj_rbi = [p for p in [
                player.projected_rbi,
                player.br_proj_rbi,
                player.fg_steamer_rbi,
                player.fg_zips_rbi,
                player.fg_atc_rbi
            ] if p is not None]
            proj_sb = [p for p in [
                player.projected_stolen_bases,
                player.br_proj_sb,
                player.fg_steamer_sb,
                player.fg_zips_sb,
                player.fg_atc_sb
            ] if p is not None]
            proj_obp = [p for p in [
                player.projected_obp,
                player.br_proj_obp,
                player.fg_steamer_obp,
                player.fg_zips_obp,
                player.fg_atc_obp
            ] if p is not None]
            
            features['avg_proj_hr'] = np.mean(proj_hr) if proj_hr else 0
            features['avg_proj_r'] = np.mean(proj_r) if proj_r else 0
            features['avg_proj_rbi'] = np.mean(proj_rbi) if proj_rbi else 0
            features['avg_proj_sb'] = np.mean(proj_sb) if proj_sb else 0
            features['avg_proj_obp'] = np.mean(proj_obp) if proj_obp else 0.3
            features['proj_std_hr'] = np.std(proj_hr) if len(proj_hr) > 1 else 0
        
        return features
    
    def _extract_advanced_metrics(self, player: Player, is_pitcher: bool) -> Dict[str, float]:
        """Extract advanced metric features."""
        features = {}
        
        if is_pitcher:
            features['br_era_plus'] = player.br_era_plus or 100
            features['br_fip'] = player.br_fip or 4.0
            features['br_xfip'] = player.br_xfip or 4.0
        else:
            features['br_wrc_plus'] = player.br_wrc_plus or 100
            features['br_ops_plus'] = player.br_ops_plus or 100
        
        features['br_war'] = player.br_war or 0
        
        return features
    
    def _extract_statcast_features(self, player: Player, is_pitcher: bool) -> Dict[str, float]:
        """Extract Statcast features."""
        features = {}
        
        if is_pitcher:
            features['savant_spin_rate'] = player.savant_spin_rate or 0
            features['savant_velocity'] = player.savant_velocity or 0
        else:
            features['savant_exit_velocity'] = player.savant_exit_velocity or 0
            features['savant_barrel_rate'] = player.savant_barrel_rate or 0
            features['savant_hard_hit_rate'] = player.savant_hard_hit_rate or 0
            features['savant_xba'] = player.savant_xba or 0
            features['savant_xwoba'] = player.savant_xwoba or 0
            features['savant_sprint_speed'] = player.savant_sprint_speed or 0
        
        features['park_factor_offense'] = player.park_factor_offense or 1.0
        features['park_factor_hr'] = player.park_factor_hr or 1.0
        
        return features
    
    def _extract_risk_features(self, player: Player) -> Dict[str, float]:
        """Extract risk-related features."""
        features = {
            'injury_risk_score': player.injury_risk_score or 0.0,
            'sample_size_confidence': player.sample_size_confidence or 0.5,
            'age_decline_factor': player.age_decline_factor or 1.0,
            'age': player.age or 27,
            'news_sentiment': player.news_sentiment or 0.0,
            'contract_year': 1.0 if player.contract_year else 0.0,
            'big_contract': 1.0 if player.big_contract else 0.0,
            'prospect_called_up': 1.0 if player.prospect_called_up else 0.0,
            'current_injury': 1.0 if player.current_injury else 0.0,
            'injury_history_count': len(player.injury_history),
        }
        return features
    
    def _extract_context_features(
        self, player: Player, current_pick: int, round_num: int
    ) -> Dict[str, float]:
        """Extract draft context features."""
        features = {
            'pick_number': current_pick,
            'round': round_num,
            'bb_forecaster_pred': player.bb_forecaster_prediction or 0.0,
        }
        return features
    
    def _extract_team_state_features(self, my_team: List[Player], is_pitcher: bool) -> Dict[str, float]:
        """Extract current team state features."""
        pitcher_count = sum(1 for p in my_team if p.position in ['SP', 'RP', 'P'])
        hitter_count = len(my_team) - pitcher_count
        
        # Calculate current category totals
        totals = self.standings_calculator._calculate_team_totals(my_team)
        
        features = {
            'roster_size': len(my_team),
            'hitters_on_roster': hitter_count,
            'pitchers_on_roster': pitcher_count,
            'current_hr': totals.get('HR', 0),
            'current_r': totals.get('R', 0),
            'current_rbi': totals.get('RBI', 0),
            'current_sb': totals.get('SB', 0),
            'current_obp': totals.get('OBP', 0),
            'current_w': totals.get('W', 0),
            'current_k': totals.get('K', 0),
            'current_era': totals.get('ERA', 0),
            'current_whip': totals.get('WHIP', 0),
        }
        return features
    
    def _extract_position_scarcity(
        self,
        player: Player,
        all_players: List[Player],
        draft_state: DraftState,
        all_team_rosters: Dict[str, List[Player]]
    ) -> Dict[str, float]:
        """Extract position scarcity features."""
        player_pos = player.position
        
        # Count drafted at position
        drafted_at_pos = sum(
            1 for roster in all_team_rosters.values()
            for p in roster
            if p.position == player_pos
        )
        
        # Count available at position
        available_at_pos = sum(1 for p in all_players if p.position == player_pos)
        
        # Calculate scarcity
        total_needed = draft_state.total_teams * self._get_position_requirement(player_pos)
        slots_remaining = max(0, total_needed - drafted_at_pos)
        
        features = {
            'drafted_at_position': drafted_at_pos,
            'available_at_position': available_at_pos,
            'slots_remaining': slots_remaining,
            'position_scarcity_ratio': available_at_pos / max(1, slots_remaining),
        }
        
        return features
    
    def _extract_comparative_advantage(
        self,
        player: Player,
        my_team: List[Player],
        all_team_rosters: Dict[str, List[Player]],
        league_thresholds: Optional[Dict[str, float]],
        my_team_name: Optional[str] = None
    ) -> Dict[str, float]:
        """Extract comparative advantage features.
        
        Args:
            player: Player being evaluated
            my_team: Current roster
            all_team_rosters: All team rosters
            league_thresholds: Stats needed to win each category
            my_team_name: Name of my team (for excluding from opponent comparisons)
        """
        features = {}
        
        # Calculate my current totals
        my_totals = self.standings_calculator._calculate_team_totals(my_team)
        
        # Calculate projected totals with this player
        projected_team = my_team + [player]
        projected_totals = self.standings_calculator._calculate_team_totals(projected_team)
        
        # Calculate improvements
        improvements = {}
        for category in ['HR', 'R', 'RBI', 'SB', 'W', 'K']:
            improvements[category] = projected_totals.get(category, 0) - my_totals.get(category, 0)
        
        # Count how many opponents I'd pass with this improvement
        for category, improvement in improvements.items():
            if improvement > 0:
                my_value = my_totals.get(category, 0)
                opponents_ahead = sum(
                    1 for team_name, roster in all_team_rosters.items()
                    if my_team_name is None or team_name != my_team_name
                    for opp_totals in [self.standings_calculator._calculate_team_totals(roster)]
                    if opp_totals.get(category, 0) > my_value
                )
                features[f'improves_{category.lower()}'] = improvement
                features[f'passes_{category.lower()}_opponents'] = opponents_ahead
        
        # Compare to league thresholds
        if league_thresholds:
            for category, threshold in league_thresholds.items():
                my_value = my_totals.get(category, 0)
                features[f'gap_to_{category.lower()}_threshold'] = max(0, threshold - my_value)
                features[f'above_{category.lower()}_threshold'] = 1.0 if my_value >= threshold else 0.0
        
        return features
    
    def _extract_adp_features(self, player: Player, current_pick: int) -> Dict[str, float]:
        """Extract ADP features with dynamic weighting."""
        features = {}
        
        # Use NFBC ADP if available, otherwise regular ADP
        adp = player.nfbc_adp or player.adp
        
        if adp:
            adp_diff = current_pick - adp  # Negative = early, positive = late
            
            # Dynamic ADP relevance (decreases after round 15)
            if current_pick <= 195:  # Rounds 1-15 (13 teams * 15 rounds)
                adp_relevance = 1.0
            elif current_pick <= 260:  # Rounds 16-20
                adp_relevance = 0.5
            else:  # Round 21+
                adp_relevance = 0.1
            
            features['adp'] = adp
            features['adp_diff'] = adp_diff
            features['adp_relevance'] = adp_relevance
            features['adp_weighted_diff'] = adp_diff * adp_relevance
        else:
            features['adp'] = 999
            features['adp_diff'] = 0
            features['adp_relevance'] = 0
            features['adp_weighted_diff'] = 0
        
        return features
    
    def _get_position_requirement(self, position: str) -> int:
        """Get position requirement for Bob Uecker League."""
        requirements = {
            'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1,
            'MI': 1, 'CI': 1, 'OF': 4, 'U': 1, 'P': 9, 'SP': 9, 'RP': 9
        }
        return requirements.get(position, 1)



