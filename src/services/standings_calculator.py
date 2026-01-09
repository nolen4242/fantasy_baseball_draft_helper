"""Calculate fantasy standings from team rosters."""
from typing import List, Dict, Tuple
from src.models.player import Player
import numpy as np
import hashlib


class StandingsCalculator:
    """Calculates category standings and final rankings."""
    
    # Bob Uecker League categories
    BATTING_CATEGORIES = ['HR', 'OBP', 'R', 'RBI', 'SB']
    PITCHING_CATEGORIES = ['ERA', 'K', 'SHOLDS', 'WHIP', 'WQS']
    
    def __init__(self):
        # Cache for standings calculations
        self._standings_cache: Dict[str, Dict] = {}
        self._team_totals_cache: Dict[str, Dict[str, float]] = {}
    
    def _get_roster_hash(self, team_rosters: Dict[str, List[Player]]) -> str:
        """Generate hash of team rosters for cache invalidation."""
        roster_str = ""
        for team in sorted(team_rosters.keys()):
            player_ids = sorted([p.player_id for p in team_rosters[team]])
            roster_str += f"{team}:{','.join(player_ids)};"
        return hashlib.md5(roster_str.encode()).hexdigest()[:16]
    
    def get_cached_team_totals(self, roster: List[Player]) -> Dict[str, float]:
        """Get team totals with caching."""
        cache_key = ','.join(sorted([p.player_id for p in roster]))
        if cache_key not in self._team_totals_cache:
            self._team_totals_cache[cache_key] = self._calculate_team_totals(roster)
        return self._team_totals_cache[cache_key]
    
    def clear_cache(self):
        """Clear all caches."""
        self._standings_cache.clear()
        self._team_totals_cache.clear()
    
    def calculate_standings(self, team_rosters: Dict[str, List[Player]], use_cache: bool = True) -> Dict:
        """
        Calculate category standings for all teams.
        
        Returns:
            Dictionary with:
            - category_totals: Dict[team_name, Dict[category, value]]
            - category_rankings: Dict[category, List[team_name]] (sorted by rank)
            - total_points: Dict[team_name, int] (sum of category ranks)
            - final_rankings: List[team_name] (sorted by total points, descending)
        """
        # Check cache first
        if use_cache:
            cache_key = self._get_roster_hash(team_rosters)
            if cache_key in self._standings_cache:
                return self._standings_cache[cache_key]
        
        category_totals = {}
        
        # Calculate totals for each team (using caching for individual teams)
        for team_name, roster in team_rosters.items():
            totals = self.get_cached_team_totals(roster)
            category_totals[team_name] = totals
        
        # Calculate rankings for each category
        category_rankings = {}
        for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES:
            rankings = self._rank_teams_by_category(category, category_totals)
            category_rankings[category] = rankings
        
        # Calculate total points (roto scoring: lowest = 1 point, highest = 13 points)
        # For ties, points are split between tied teams
        # In a 13-team league: lowest = 1 point, highest = 13 points
        num_teams = len(team_rosters)
        total_points = {}
        
        # Calculate points for each category with tie handling
        category_points = {}  # Dict[category, Dict[team_name, points]]
        for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES:
            category_points[category] = self._calculate_category_points(
                category, category_totals, category_rankings, num_teams
            )
        
        # Sum up points across all categories
        for team_name in team_rosters.keys():
            total_points[team_name] = sum(
                category_points[category].get(team_name, 0)
                for category in self.BATTING_CATEGORIES + self.PITCHING_CATEGORIES
            )
        
        # Final rankings (higher total points = better)
        final_rankings = sorted(
            team_rosters.keys(),
            key=lambda t: total_points[t],
            reverse=True  # Higher points = better
        )
        
        result = {
            'category_totals': category_totals,
            'category_rankings': category_rankings,
            'category_points': category_points,  # Include category_points in return
            'total_points': total_points,
            'final_rankings': final_rankings
        }
        
        # Store in cache
        if use_cache:
            cache_key = self._get_roster_hash(team_rosters)
            self._standings_cache[cache_key] = result
        
        return result
    
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
        """Rank teams by a category.
        
        For ALL PITCHING categories: Teams below IP minimum get worst rank (tied for last).
        For ERA/WHIP: Lower = better rank (higher points).
        For other categories: Higher = better rank (higher points).
        """
        IP_MIN = 1000.0
        PITCHING_CATEGORIES = ['ERA', 'WHIP', 'K', 'SHOLDS', 'WQS']
        
        # For ALL pitching categories, handle IP minimum requirement
        if category in PITCHING_CATEGORIES:
            # Separate teams into those meeting IP minimum and those below
            teams_meeting_min = []
            teams_below_min = []
            
            for team, totals in category_totals.items():
                if totals.get('_below_ip_minimum', False) or totals.get('IP', 0) < IP_MIN:
                    teams_below_min.append((team, totals[category]))
                else:
                    teams_meeting_min.append((team, totals[category]))
            
            # For ERA/WHIP: lower is better (sort ascending)
            # For other pitching categories: higher is better (sort descending)
            if category in ['ERA', 'WHIP']:
                teams_meeting_min.sort(key=lambda x: x[1])  # Sort ascending (lower = better)
            else:
                teams_meeting_min.sort(key=lambda x: x[1], reverse=True)  # Sort descending (higher = better)
            
            ranked_meeting = [team for team, _ in teams_meeting_min]
            
            # Teams below minimum all get worst rank (tied for last)
            # They'll be ranked after all teams meeting minimum
            ranked_below = [team for team, _ in teams_below_min]
            
            # Combine: teams meeting minimum first (ranked), then teams below minimum (all tied for worst)
            return ranked_meeting + ranked_below
        else:
            # For batting categories, higher is better
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
    
    def _calculate_category_points(
        self,
        category: str,
        category_totals: Dict[str, Dict[str, float]],
        category_rankings: Dict[str, List[str]],
        num_teams: int
    ) -> Dict[str, float]:
        """
        Calculate roto points for a category with tie handling.
        
        Lowest value = 1 point, highest value = 13 points.
        For ties, points are split between tied teams.
        
        For ERA/WHIP: lowest value = 13 points (best), highest = 1 point (worst)
        For other categories: highest value = 13 points (best), lowest = 1 point (worst)
        """
        rankings = category_rankings.get(category, [])
        if not rankings:
            return {}
        
        IP_MIN = 1000.0
        PITCHING_CATEGORIES = ['ERA', 'WHIP', 'K', 'SHOLDS', 'WQS']
        
        # Get values for all teams
        team_values = {
            team: category_totals[team][category]
            for team in rankings
        }
        
        # Separate teams by IP minimum for pitching categories
        teams_meeting_min = []
        teams_below_min = []
        
        if category in PITCHING_CATEGORIES:
            for team in rankings:
                ip = category_totals[team].get('IP', 0)
                if ip < IP_MIN:
                    teams_below_min.append(team)
                else:
                    teams_meeting_min.append(team)
        else:
            teams_meeting_min = rankings
        
        # Group teams by value to identify ties (only for teams meeting minimum)
        # Round values to avoid floating point precision issues
        value_to_teams = {}
        for team in teams_meeting_min:
            value = team_values[team]
            # Round to avoid floating point issues (use 2 decimal places for ERA/WHIP, 1 for others)
            if category in ['ERA', 'WHIP']:
                rounded_value = round(value, 2)
            else:
                rounded_value = round(value, 1)
            
            if rounded_value not in value_to_teams:
                value_to_teams[rounded_value] = []
            value_to_teams[rounded_value].append(team)
        
        # Determine if lower or higher is better
        is_lower_better = category in ['ERA', 'WHIP']
        
        # Sort unique values (best first)
        # For ERA/WHIP: ascending (lowest first = best)
        # For others: descending (highest first = best)
        unique_values = sorted(value_to_teams.keys(), reverse=not is_lower_better)
        
        # Assign points
        points = {}
        current_rank = 1
        
        # Assign points to teams meeting minimum (ranked by value)
        for value in unique_values:
            tied_teams = value_to_teams[value]
            num_tied = len(tied_teams)
            
            # Calculate points for tied teams
            # If teams are tied at rank N, they share points for ranks N through N+num_tied-1
            # Points formula: num_teams - rank + 1 (rank 1 = 13 points, rank 13 = 1 point)
            # Sum points for all ranks in the tie, then divide by number of tied teams
            points_sum = 0
            for rank in range(current_rank, current_rank + num_tied):
                rank_points = num_teams - rank + 1
                points_sum += rank_points
            
            points_per_team = points_sum / num_tied
            
            # Assign points to all tied teams
            for team in tied_teams:
                points[team] = points_per_team
            
            current_rank += num_tied
        
        # Teams below IP minimum all get 1 point (worst) in pitching categories
        for team in teams_below_min:
            points[team] = 1.0
        
        return points
    
    def _get_team_rank(self, team_name: str, category: str, category_rankings: Dict[str, List[str]]) -> int:
        """Get a team's rank in a category (1 = best)."""
        rankings = category_rankings.get(category, [])
        try:
            return rankings.index(team_name) + 1
        except ValueError:
            return len(rankings) + 1

