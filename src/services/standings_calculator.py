"""Calculate fantasy standings from team rosters."""
from typing import List, Dict
from src.models.player import Player
import numpy as np


class StandingsCalculator:
    """Calculates category standings and final rankings."""
    
    # Bob Uecker League categories
    BATTING_CATEGORIES = ['HR', 'OBP', 'R', 'RBI', 'SB']
    PITCHING_CATEGORIES = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']
    
    def calculate_standings(self, team_rosters: Dict[str, List[Player]]) -> Dict:
        """
        Calculate category standings for all teams.
        
        Returns:
            Dictionary with:
            - category_totals: Dict[team_name, Dict[category, value]]
            - category_rankings: Dict[category, List[team_name]] (sorted by rank)
            - total_points: Dict[team_name, int] (sum of category ranks)
            - final_rankings: List[team_name] (sorted by total points, descending)
        """
        category_totals = {}
        
        # Calculate totals for each team
        for team_name, roster in team_rosters.items():
            totals = self._calculate_team_totals(roster)
            category_totals[team_name] = totals
        
        # Calculate rankings for each category
        category_rankings = {}
        for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES:
            rankings = self._rank_teams_by_category(category, category_totals)
            category_rankings[category] = rankings
        
        # Calculate total points (sum of category ranks)
        total_points = {}
        for team_name in team_rosters.keys():
            points = sum(
                self._get_team_rank(team_name, category, category_rankings)
                for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES
            )
            total_points[team_name] = points
        
        # Final rankings (lower total points = better, like golf)
        final_rankings = sorted(
            team_rosters.keys(),
            key=lambda t: total_points[t]
        )
        
        return {
            'category_totals': category_totals,
            'category_rankings': category_rankings,
            'total_points': total_points,
            'final_rankings': final_rankings
        }
    
    def _calculate_team_totals(self, roster: List[Player]) -> Dict[str, float]:
        """Calculate category totals for a single team."""
        totals = {
            'HR': 0.0, 'OBP': 0.0, 'R': 0.0, 'RBI': 0.0, 'SB': 0.0,
            'W': 0.0, 'QS': 0.0, 'K': 0.0, 'SV': 0.0, 'HD': 0.0,
            'ERA': 0.0, 'WHIP': 0.0, 'IP': 0.0
        }
        
        hitters = []
        pitchers = []
        
        for player in roster:
            is_hitter = player.position not in ['SP', 'RP', 'P']
            if is_hitter:
                hitters.append(player)
            else:
                pitchers.append(player)
        
        # Batting categories
        for hitter in hitters:
            totals['HR'] += hitter.projected_home_runs or 0
            totals['R'] += hitter.projected_runs or 0
            totals['RBI'] += hitter.projected_rbi or 0
            totals['SB'] += hitter.projected_stolen_bases or 0
        
        # OBP is averaged (weighted by plate appearances, but we'll use simple average)
        if hitters:
            obp_sum = sum(h.projected_obp for h in hitters if h.projected_obp)
            totals['OBP'] = obp_sum / len(hitters) if obp_sum > 0 else 0
        
        # Pitching categories
        for pitcher in pitchers:
            totals['W'] += pitcher.projected_wins or 0
            totals['QS'] += pitcher.projected_quality_starts or 0
            totals['K'] += pitcher.projected_strikeouts or 0
            totals['SV'] += pitcher.projected_saves or 0
            totals['HD'] += pitcher.projected_holds or 0
        
        # WQS = Wins + Quality Starts
        totals['WQS'] = totals['W'] + totals['QS']
        
        # SHOLDS = Saves + (Holds * 0.5)
        totals['SHOLDS'] = totals['SV'] + (totals['HD'] * 0.5)
        
        # ERA and WHIP are averaged (weighted by innings, but we'll use simple average)
        if pitchers:
            era_sum = sum(p.projected_era for p in pitchers if p.projected_era)
            whip_sum = sum(p.projected_whip for p in pitchers if p.projected_whip)
            totals['ERA'] = era_sum / len(pitchers) if era_sum > 0 else 0
            totals['WHIP'] = whip_sum / len(pitchers) if whip_sum > 0 else 0
        
        return totals
    
    def _rank_teams_by_category(self, category: str, category_totals: Dict[str, Dict[str, float]]) -> List[str]:
        """Rank teams by a category (higher is better, except ERA/WHIP)."""
        team_values = {
            team: totals[category]
            for team, totals in category_totals.items()
        }
        
        # For ERA and WHIP, lower is better
        reverse = category not in ['ERA', 'WHIP']
        
        ranked = sorted(
            team_values.keys(),
            key=lambda t: team_values[t],
            reverse=reverse
        )
        
        return ranked
    
    def _get_team_rank(self, team_name: str, category: str, category_rankings: Dict[str, List[str]]) -> int:
        """Get a team's rank in a category (1 = best)."""
        rankings = category_rankings.get(category, [])
        try:
            return rankings.index(team_name) + 1
        except ValueError:
            return len(rankings) + 1

