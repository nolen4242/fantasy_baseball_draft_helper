"""Custom ADP calculator for Bob Uecker League format."""
from typing import List, Dict, Optional
from src.models.player import Player


class CustomADPCalculator:
    """
    Calculates custom ADP based on Bob Uecker League categories.
    Ranks players by their value in the specific league format.
    """
    
    # League categories
    BATTING_CATEGORIES = ['HR', 'OBP', 'R', 'RBI', 'SB']
    PITCHING_CATEGORIES = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']
    
    def calculate_custom_adp(self, players: List[Player]) -> Dict[str, float]:
        """
        Calculate custom ADP for all players based on league-specific value.
        
        Args:
            players: List of all players with projections
        
        Returns:
            Dictionary mapping player_id to custom ADP (1 = best, higher = worse)
        """
        # Separate hitters and pitchers
        hitters = [p for p in players if p.position not in ['SP', 'RP', 'P']]
        pitchers = [p for p in players if p.position in ['SP', 'RP', 'P']]
        
        # Calculate value scores
        hitter_scores = {}
        for hitter in hitters:
            score = self._calculate_hitter_value(hitter)
            hitter_scores[hitter.player_id] = score
        
        pitcher_scores = {}
        for pitcher in pitchers:
            score = self._calculate_pitcher_value(pitcher)
            pitcher_scores[pitcher.player_id] = score
        
        # Rank within each group
        hitter_rankings = self._rank_players(hitter_scores)
        pitcher_rankings = self._rank_players(pitcher_scores)
        
        # Combine rankings (hitters and pitchers interleaved based on value)
        # This creates a unified ADP that reflects overall value
        all_scores = {**hitter_scores, **pitcher_scores}
        all_rankings = self._rank_players(all_scores)
        
        return all_rankings
    
    def _calculate_hitter_value(self, player: Player) -> float:
        """
        Calculate value score for a hitter based on Bob Uecker League categories.
        Categories: HR, OBP, R, RBI, SB
        """
        value = 0.0
        
        # Use best available projection (prefer consensus/average)
        hr = self._get_best_projection(player, 'hr')
        r = self._get_best_projection(player, 'r')
        rbi = self._get_best_projection(player, 'rbi')
        sb = self._get_best_projection(player, 'sb')
        obp = self._get_best_projection(player, 'obp')
        
        # Weight categories based on scarcity and importance
        # HR: High value, moderate scarcity
        value += (hr or 0) * 2.5
        
        # R: Moderate value, less scarce
        value += (r or 0) * 0.6
        
        # RBI: Moderate value, less scarce
        value += (rbi or 0) * 0.6
        
        # SB: High value, high scarcity
        value += (sb or 0) * 3.5
        
        # OBP: High value, rate stat (normalize to 0.300 baseline)
        if obp:
            value += (obp - 0.300) * 500
        
        # Apply risk adjustments
        value = self._apply_risk_adjustments(value, player)
        
        # Apply park factor adjustments
        if player.park_factor_offense:
            value *= player.park_factor_offense
        
        return value
    
    def _calculate_pitcher_value(self, player: Player) -> float:
        """
        Calculate value score for a pitcher based on Bob Uecker League categories.
        Categories: ERA, K, SHOLDS, WHIP, WQS
        """
        value = 0.0
        
        # Use best available projection
        w = self._get_best_projection(player, 'w')
        qs = self._get_best_projection(player, 'qs')
        k = self._get_best_projection(player, 'k')
        sv = self._get_best_projection(player, 'sv')
        hd = self._get_best_projection(player, 'hd')
        era = self._get_best_projection(player, 'era')
        whip = self._get_best_projection(player, 'whip')
        
        # WQS: Wins + Quality Starts (combined category)
        wqs = (w or 0) + (qs or 0)
        value += wqs * 2.0
        
        # K: Strikeouts (counting stat)
        value += (k or 0) * 0.25
        
        # SHOLDS: Saves + Holds (Holds count as 0.5)
        sholds = (sv or 0) + ((hd or 0) * 0.5)
        value += sholds * 3.0
        
        # ERA: Lower is better (invert)
        if era:
            # Penalize high ERA, reward low ERA
            # Baseline is 4.00, so 3.00 ERA = +15 points, 5.00 ERA = -15 points
            value += max(0, (4.00 - era) * 15)
        
        # WHIP: Lower is better (invert)
        if whip:
            # Baseline is 1.30, so 1.10 WHIP = +6 points, 1.50 WHIP = -6 points
            value += max(0, (1.30 - whip) * 30)
        
        # Apply risk adjustments
        value = self._apply_risk_adjustments(value, player)
        
        # Apply park factor adjustments (pitching park factor)
        if player.park_factor_pitching:
            # Lower park factor = better for pitchers (fewer runs allowed)
            # Invert: 0.95 park factor = 1.05 multiplier
            park_multiplier = 2.0 - player.park_factor_pitching
            value *= park_multiplier
        
        return value
    
    def _get_best_projection(self, player: Player, stat: str) -> Optional[float]:
        """
        Get best available projection for a stat.
        Prefers consensus/average across multiple systems.
        """
        if stat == 'hr':
            proj = [p for p in [
                player.projected_home_runs,
                player.br_proj_hr,
                player.fg_steamer_hr,
                player.fg_zips_hr,
                player.fg_thebat_hr,
                player.fg_atc_hr
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'r':
            proj = [p for p in [
                player.projected_runs,
                player.br_proj_r,
                player.fg_steamer_r,
                player.fg_zips_r,
                player.fg_atc_r
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'rbi':
            proj = [p for p in [
                player.projected_rbi,
                player.br_proj_rbi,
                player.fg_steamer_rbi,
                player.fg_zips_rbi,
                player.fg_atc_rbi
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'sb':
            proj = [p for p in [
                player.projected_stolen_bases,
                player.br_proj_sb,
                player.fg_steamer_sb,
                player.fg_zips_sb,
                player.fg_atc_sb
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'obp':
            proj = [p for p in [
                player.projected_obp,
                player.br_proj_obp,
                player.fg_steamer_obp,
                player.fg_zips_obp,
                player.fg_atc_obp
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'w':
            proj = [p for p in [
                player.projected_wins,
                player.br_proj_w,
                player.fg_steamer_w,
                player.fg_zips_w,
                player.fg_atc_w
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'qs':
            return player.projected_quality_starts
        
        elif stat == 'k':
            proj = [p for p in [
                player.projected_strikeouts,
                player.br_proj_k,
                player.fg_steamer_k,
                player.fg_zips_k,
                player.fg_atc_k
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'sv':
            return player.projected_saves
        
        elif stat == 'hd':
            return player.projected_holds
        
        elif stat == 'era':
            proj = [p for p in [
                player.projected_era,
                player.br_proj_era,
                player.fg_steamer_era,
                player.fg_zips_era,
                player.fg_atc_era
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        elif stat == 'whip':
            proj = [p for p in [
                player.projected_whip,
                player.br_proj_whip,
                player.fg_steamer_whip,
                player.fg_zips_whip,
                player.fg_atc_whip
            ] if p is not None]
            return sum(proj) / len(proj) if proj else None
        
        return None
    
    def _apply_risk_adjustments(self, value: float, player: Player) -> float:
        """Apply risk-based adjustments to player value."""
        # Injury risk: reduce value by up to 30%
        if player.injury_risk_score:
            value *= (1.0 - player.injury_risk_score * 0.3)
        
        # Sample size confidence: reduce value for low confidence (prospects)
        if player.sample_size_confidence:
            value *= player.sample_size_confidence
        
        # Age decline: apply age-based decline factor
        if player.age_decline_factor:
            value *= player.age_decline_factor
        
        # Current injury: significant penalty
        if player.current_injury:
            value *= 0.5  # 50% penalty for current injury
        
        return value
    
    def _rank_players(self, scores: Dict[str, float]) -> Dict[str, float]:
        """
        Rank players by score (lower rank = better).
        Returns dictionary mapping player_id to rank (1 = best).
        """
        # Sort by score (descending - higher score = better)
        sorted_players = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Assign ranks (1 = best)
        rankings = {}
        for rank, (player_id, score) in enumerate(sorted_players, start=1):
            rankings[player_id] = float(rank)
        
        return rankings

