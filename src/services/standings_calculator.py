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
        
        # Calculate total points (roto scoring: rank 1 = max points, rank 13 = 1 point)
        # In a 13-team league: 1st = 13 points, 2nd = 12 points, ..., 13th = 1 point
        num_teams = len(team_rosters)
        total_points = {}
        for team_name in team_rosters.keys():
            # Sum up roto points (higher rank = more points)
            roto_points = sum(
                num_teams - self._get_team_rank(team_name, category, category_rankings) + 1
                for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES
            )
            total_points[team_name] = roto_points
        
        # Final rankings (higher total points = better)
        final_rankings = sorted(
            team_rosters.keys(),
            key=lambda t: total_points[t],
            reverse=True  # Higher points = better
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
        
        # Pitching categories - calculate IP first
        total_ip = 0.0
        ip_weighted_era_sum = 0.0
        ip_weighted_whip_sum = 0.0
        
        for pitcher in pitchers:
            # Get IP - use projected_innings_pitched, or estimate from QS (QS * 6.5 avg IP per start)
            # or from GS if available, or use br_innings_pitched as fallback
            pitcher_ip = pitcher.projected_innings_pitched
            if pitcher_ip is None:
                # Estimate from QS (quality starts typically ~6.5 IP each)
                if pitcher.projected_quality_starts:
                    pitcher_ip = pitcher.projected_quality_starts * 6.5
                # Fallback: estimate from saves (relief pitchers ~1 IP per save)
                elif pitcher.projected_saves:
                    pitcher_ip = pitcher.projected_saves * 1.0
                # Final fallback: use br_innings_pitched if available
                elif hasattr(pitcher, 'br_innings_pitched') and pitcher.br_innings_pitched:
                    pitcher_ip = pitcher.br_innings_pitched
                else:
                    # Default estimate: 150 IP for SP, 60 IP for RP
                    if pitcher.position == 'SP':
                        pitcher_ip = 150.0
                    else:
                        pitcher_ip = 60.0
            
            # Cap IP at maximum (1400 total for team)
            # We'll apply the cap after summing all IP
            total_ip += pitcher_ip
            
            # Calculate IP-weighted ERA and WHIP
            if pitcher.projected_era:
                ip_weighted_era_sum += pitcher.projected_era * pitcher_ip
            if pitcher.projected_whip:
                ip_weighted_whip_sum += pitcher.projected_whip * pitcher_ip
            
            # Counting stats (not affected by IP limits until we hit 1400)
            totals['W'] += pitcher.projected_wins or 0
            totals['QS'] += pitcher.projected_quality_starts or 0
            totals['K'] += pitcher.projected_strikeouts or 0
            totals['SV'] += pitcher.projected_saves or 0
            totals['HD'] += pitcher.projected_holds or 0
        
        # Apply 1400 IP maximum - if exceeded, scale down counting stats proportionally
        IP_MAX = 1400.0
        IP_MIN = 1000.0
        
        if total_ip > IP_MAX:
            # Scale down counting stats proportionally
            scale_factor = IP_MAX / total_ip
            totals['W'] *= scale_factor
            totals['QS'] *= scale_factor
            totals['K'] *= scale_factor
            totals['SV'] *= scale_factor
            totals['HD'] *= scale_factor
            # Also scale IP-weighted sums
            ip_weighted_era_sum *= scale_factor
            ip_weighted_whip_sum *= scale_factor
            total_ip = IP_MAX
        
        # WQS = Wins + Quality Starts
        totals['WQS'] = totals['W'] + totals['QS']
        
        # SHOLDS = Saves + (Holds * 0.5)
        totals['SHOLDS'] = totals['SV'] + (totals['HD'] * 0.5)
        
        # ERA and WHIP: IP-weighted average
        # Calculate actual ERA/WHIP regardless of IP minimum (we'll handle ranking separately)
        if total_ip > 0 and ip_weighted_era_sum > 0:
            totals['ERA'] = ip_weighted_era_sum / total_ip
        else:
            totals['ERA'] = 0.0
        
        if total_ip > 0 and ip_weighted_whip_sum > 0:
            totals['WHIP'] = ip_weighted_whip_sum / total_ip
        else:
            totals['WHIP'] = 0.0
        
        # Store IP and minimum flag for ranking
        totals['IP'] = total_ip
        totals['_below_ip_minimum'] = total_ip < IP_MIN
        
        return totals
    
    def _rank_teams_by_category(self, category: str, category_totals: Dict[str, Dict[str, float]]) -> List[str]:
        """Rank teams by a category (higher is better, except ERA/WHIP).
        
        For ERA/WHIP: Teams below IP minimum get worst rank (13th in 13-team league).
        Otherwise, lower ERA/WHIP = better rank.
        """
        IP_MIN = 1000.0
        
        # For ERA and WHIP, handle IP minimum requirement
        if category in ['ERA', 'WHIP']:
            # Separate teams into those meeting IP minimum and those below
            teams_meeting_min = []
            teams_below_min = []
            
            for team, totals in category_totals.items():
                if totals.get('_below_ip_minimum', False) or totals.get('IP', 0) < IP_MIN:
                    teams_below_min.append((team, totals[category]))
                else:
                    teams_meeting_min.append((team, totals[category]))
            
            # Rank teams meeting minimum (lower is better for ERA/WHIP)
            teams_meeting_min.sort(key=lambda x: x[1])  # Sort by value, ascending (lower = better)
            ranked_meeting = [team for team, _ in teams_meeting_min]
            
            # Teams below minimum all get worst rank (tied for last)
            # They'll be ranked after all teams meeting minimum
            ranked_below = [team for team, _ in teams_below_min]
            
            # Combine: teams meeting minimum first (ranked), then teams below minimum (all tied for worst)
            return ranked_meeting + ranked_below
        else:
            # For other categories, higher is better
            team_values = {
                team: totals[category]
                for team, totals in category_totals.items()
            }
            
            ranked = sorted(
                team_values.keys(),
                key=lambda t: team_values[t],
                reverse=True  # Higher is better
            )
            
            return ranked
    
    def _get_team_rank(self, team_name: str, category: str, category_rankings: Dict[str, List[str]]) -> int:
        """Get a team's rank in a category (1 = best)."""
        rankings = category_rankings.get(category, [])
        try:
            return rankings.index(team_name) + 1
        except ValueError:
            return len(rankings) + 1

