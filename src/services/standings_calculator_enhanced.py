"""Enhanced standings calculator with filtering and individual stat rankings."""
from typing import List, Dict, Optional, Tuple
from src.models.player import Player
from src.services.standings_calculator import StandingsCalculator


class StandingsCalculatorEnhanced(StandingsCalculator):
    """Enhanced standings calculator with filtering and sorting capabilities."""
    
    def get_individual_stat_rankings(
        self,
        team_rosters: Dict[str, List[Player]],
        stat: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get rankings for an individual stat across all teams.
        
        Args:
            team_rosters: Dictionary of team name to list of players
            stat: Stat to rank by (e.g., 'HR', 'ERA', 'K')
            limit: Optional limit on number of results
            
        Returns:
            List of dicts with team_name, value, rank
        """
        # Calculate totals for all teams
        category_totals = {}
        for team_name, roster in team_rosters.items():
            totals = self.get_cached_team_totals(roster)
            category_totals[team_name] = totals
        
        # Get values for the requested stat
        team_values = []
        for team_name, totals in category_totals.items():
            value = totals.get(stat, 0)
            ip = totals.get('IP', 0)
            below_min = totals.get('_below_ip_minimum', False)
            
            team_values.append({
                'team_name': team_name,
                'value': value,
                'ip': ip,
                'below_ip_minimum': below_min
            })
        
        # Sort based on stat type
        is_lower_better = stat in ['ERA', 'WHIP']
        is_pitching_stat = stat in self.PITCHING_CATEGORIES
        
        # For pitching stats, separate teams by IP minimum
        if is_pitching_stat:
            teams_meeting_min = [t for t in team_values if not t['below_ip_minimum']]
            teams_below_min = [t for t in team_values if t['below_ip_minimum']]
            
            # Sort teams meeting minimum
            teams_meeting_min.sort(key=lambda x: x['value'], reverse=not is_lower_better)
            
            # Combine: teams meeting minimum first, then teams below minimum
            sorted_teams = teams_meeting_min + teams_below_min
        else:
            # For batting stats, higher is always better
            sorted_teams = sorted(team_values, key=lambda x: x['value'], reverse=True)
        
        # Add ranks
        for rank, team in enumerate(sorted_teams, 1):
            team['rank'] = rank
        
        # Apply limit if specified
        if limit:
            sorted_teams = sorted_teams[:limit]
        
        return sorted_teams
    
    def get_filtered_standings(
        self,
        team_rosters: Dict[str, List[Player]],
        sort_by: Optional[str] = None,
        filter_category: Optional[str] = None,
        filter_min_value: Optional[float] = None,
        filter_max_value: Optional[float] = None
    ) -> Dict:
        """
        Get standings with filtering and custom sorting.
        
        Args:
            team_rosters: Dictionary of team name to list of players
            sort_by: Category to sort by (default: total_points)
            filter_category: Category to filter by
            filter_min_value: Minimum value for filter
            filter_max_value: Maximum value for filter
            
        Returns:
            Filtered and sorted standings
        """
        # Calculate base standings
        standings = self.calculate_standings(team_rosters, use_cache=True)
        
        # Apply filtering if specified
        filtered_teams = list(team_rosters.keys())
        if filter_category and (filter_min_value is not None or filter_max_value is not None):
            filtered_teams = []
            for team_name in team_rosters.keys():
                value = standings['category_totals'][team_name].get(filter_category, 0)
                
                # Check min filter
                if filter_min_value is not None and value < filter_min_value:
                    continue
                
                # Check max filter
                if filter_max_value is not None and value > filter_max_value:
                    continue
                
                filtered_teams.append(team_name)
        
        # Apply custom sorting if specified
        if sort_by and sort_by != 'total_points':
            is_lower_better = sort_by in ['ERA', 'WHIP']
            filtered_teams.sort(
                key=lambda t: standings['category_totals'][t].get(sort_by, 0),
                reverse=not is_lower_better
            )
        else:
            # Sort by total points (default)
            filtered_teams.sort(
                key=lambda t: standings['total_points'].get(t, 0),
                reverse=True
            )
        
        # Build filtered result
        result = {
            'category_totals': {t: standings['category_totals'][t] for t in filtered_teams},
            'category_rankings': standings['category_rankings'],
            'category_points': standings['category_points'],
            'total_points': {t: standings['total_points'][t] for t in filtered_teams},
            'final_rankings': filtered_teams,
            'filter_applied': filter_category is not None,
            'sort_by': sort_by or 'total_points'
        }
        
        return result
    
    def get_category_leaders(
        self,
        team_rosters: Dict[str, List[Player]],
        category: str,
        top_n: int = 5
    ) -> List[Dict]:
        """
        Get top N teams in a specific category.
        
        Args:
            team_rosters: Dictionary of team name to list of players
            category: Category to get leaders for
            top_n: Number of leaders to return
            
        Returns:
            List of dicts with team_name, value, rank
        """
        return self.get_individual_stat_rankings(team_rosters, category, limit=top_n)
    
    def validate_pitching_calculations(
        self,
        team_rosters: Dict[str, List[Player]]
    ) -> Dict[str, Dict]:
        """
        Validate pitching calculations and return detailed breakdown.
        
        Returns:
            Dictionary with validation results for each team
        """
        validation_results = {}
        
        for team_name, roster in team_rosters.items():
            pitchers = [p for p in roster if p.position in ['SP', 'RP', 'P']]
            
            # Calculate detailed pitching stats
            total_ip = 0.0
            total_era_weighted = 0.0
            total_whip_weighted = 0.0
            total_k = 0.0
            total_w = 0.0
            total_qs = 0.0
            total_sv = 0.0
            total_hd = 0.0
            
            pitcher_details = []
            for pitcher in pitchers:
                # Get IP
                ip = pitcher.projected_innings_pitched or 0
                if ip == 0 and pitcher.projected_quality_starts:
                    ip = pitcher.projected_quality_starts * 6.5
                elif ip == 0 and pitcher.projected_saves:
                    ip = pitcher.projected_saves * 1.0
                
                total_ip += ip
                
                # ERA and WHIP weighted by IP
                if pitcher.projected_era and ip > 0:
                    total_era_weighted += pitcher.projected_era * ip
                if pitcher.projected_whip and ip > 0:
                    total_whip_weighted += pitcher.projected_whip * ip
                
                # Counting stats
                total_k += pitcher.projected_strikeouts or 0
                total_w += pitcher.projected_wins or 0
                total_qs += pitcher.projected_quality_starts or 0
                total_sv += pitcher.projected_saves or 0
                total_hd += pitcher.projected_holds or 0
                
                pitcher_details.append({
                    'name': pitcher.name,
                    'position': pitcher.position,
                    'ip': ip,
                    'era': pitcher.projected_era,
                    'whip': pitcher.projected_whip,
                    'k': pitcher.projected_strikeouts,
                    'w': pitcher.projected_wins,
                    'qs': pitcher.projected_quality_starts,
                    'sv': pitcher.projected_saves,
                    'hd': pitcher.projected_holds
                })
            
            # Calculate team averages
            team_era = total_era_weighted / total_ip if total_ip > 0 else 0
            team_whip = total_whip_weighted / total_ip if total_ip > 0 else 0
            team_wqs = total_w + total_qs
            team_sholds = total_sv + (total_hd * 0.5)
            
            # Check IP minimum
            ip_min = 1000.0
            ip_max = 1400.0
            meets_minimum = total_ip >= ip_min
            exceeds_maximum = total_ip > ip_max
            
            # If exceeds maximum, calculate scaled values
            if exceeds_maximum:
                scale_factor = ip_max / total_ip
                scaled_k = total_k * scale_factor
                scaled_w = total_w * scale_factor
                scaled_qs = total_qs * scale_factor
                scaled_sv = total_sv * scale_factor
                scaled_hd = total_hd * scale_factor
                scaled_wqs = scaled_w + scaled_qs
                scaled_sholds = scaled_sv + (scaled_hd * 0.5)
            else:
                scaled_k = total_k
                scaled_w = total_w
                scaled_qs = total_qs
                scaled_sv = total_sv
                scaled_hd = total_hd
                scaled_wqs = team_wqs
                scaled_sholds = team_sholds
            
            validation_results[team_name] = {
                'total_ip': total_ip,
                'meets_ip_minimum': meets_minimum,
                'exceeds_ip_maximum': exceeds_maximum,
                'team_era': team_era,
                'team_whip': team_whip,
                'total_k': total_k,
                'scaled_k': scaled_k,
                'total_wqs': team_wqs,
                'scaled_wqs': scaled_wqs,
                'total_sholds': team_sholds,
                'scaled_sholds': scaled_sholds,
                'pitcher_count': len(pitchers),
                'pitcher_details': pitcher_details
            }
        
        return validation_results
