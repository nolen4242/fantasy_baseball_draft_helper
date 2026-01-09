"""Loads master player dictionary and converts to Player objects for production use."""
import json
from pathlib import Path
from typing import List, Optional
from src.models.player import Player
from src.services.projection_config import calculate_weighted_projection


class MasterPlayerDictLoader:
    """
    Loads master player dictionary from JSON and converts to Player objects.
    Handles all data sources: ADP, CBS, Savant, projections, park factors.
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        self.master_dict_file = project_root / "data" / "sources" / "adp" / "players.json"
    
    def load_all_players(self) -> List[Player]:
        """
        Load all players from master player dictionary.
        Converts JSON structure to Player objects with all data populated.
        """
        if not self.master_dict_file.exists():
            print(f"Warning: Master player dict not found at {self.master_dict_file}")
            return []
        
        with open(self.master_dict_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        players = []
        # Handle both list format and dict with 'players' key
        player_list = data if isinstance(data, list) else data.get('players', [])
        
        for player_data in player_list:
            player = self._convert_to_player(player_data)
            if player:
                players.append(player)
        
        # Apply IP constraint to all QS values (post-processing)
        for player in players:
            if player.projected_quality_starts and player.projected_innings_pitched:
                max_qs_from_ip = player.projected_innings_pitched / 6.0
                if player.projected_quality_starts > max_qs_from_ip:
                    player.projected_quality_starts = max_qs_from_ip
        
        print(f"Loaded {len(players)} players from master player dictionary")
        return players
    
    def _apply_qs_ip_constraint(self, qs: Optional[float], ip: Optional[float]) -> Optional[float]:
        """Apply IP constraint to QS (each QS requires at least 6 IP)."""
        if qs is None:
            return None
        if ip is None or ip <= 0:
            return qs
        max_qs_from_ip = ip / 6.0
        return min(qs, max_qs_from_ip)
    
    def _convert_to_player(self, player_data: dict) -> Optional[Player]:
        """Convert master player dict entry to Player object."""
        try:
            # Basic info
            player_id = player_data.get('unified_id', '')
            name = player_data.get('name', '')
            # Use primary_position, fallback to first position_eligibility
            position = player_data.get('primary_position', '')
            if not position:
                position_eligibility = player_data.get('position_eligibility', [])
                position = position_eligibility[0] if position_eligibility else 'U'
            team = player_data.get('team', '')
            
            if not player_id or not name:
                return None
            
            # ADP data
            adp_data = player_data.get('adp', {})
            adp = adp_data.get('nfbc') if isinstance(adp_data, dict) else None
            
            # Get projections (2025 - Steamer and DepthChart)
            projections_2025 = player_data.get('projections', {}).get('2025', {})
            steamer = projections_2025.get('steamer', {})
            depthchart = projections_2025.get('depthchart', {})
            
            # Use weighted projections (DepthChart for counting stats, Steamer for rate stats)
            is_pitcher = position == 'P'
            
            if is_pitcher:
                # Pitching projections - use weighted averages
                projected_strikeouts = calculate_weighted_projection('strikeouts', {
                    'steamer': steamer.get('strikeouts'),
                    'depthchart': depthchart.get('strikeouts')
                })
                projected_era = calculate_weighted_projection('era', {
                    'steamer': steamer.get('era'),
                    'depthchart': depthchart.get('era')
                })
                # WHIP: Try to get from projections, or calculate from components
                projected_whip = calculate_weighted_projection('whip', {
                    'steamer': steamer.get('whip'),
                    'depthchart': depthchart.get('whip')
                })
                
                # If WHIP not available, calculate from walks and IP
                if projected_whip is None:
                    # Get walks and IP from either source
                    walks_steamer = steamer.get('walks')
                    walks_depthchart = depthchart.get('walks')
                    walks = walks_steamer or walks_depthchart
                    
                    ip_steamer = steamer.get('innings_pitched')
                    ip_depthchart = depthchart.get('innings_pitched')
                    ip = ip_steamer or ip_depthchart
                    
                    if walks is not None and ip is not None and ip > 0:
                        # Estimate hits from league-average H/9 rate
                        league_avg_h_per_9 = 8.7
                        # Use BABIP if available to refine estimate
                        babip_steamer = steamer.get('babip')
                        babip_depthchart = depthchart.get('babip')
                        babip = babip_steamer or babip_depthchart
                        
                        if babip:
                            babip_factor = babip / 0.300  # Normalize to league avg BABIP
                            estimated_h_per_9 = league_avg_h_per_9 * babip_factor
                        else:
                            estimated_h_per_9 = league_avg_h_per_9
                        
                        estimated_hits = (estimated_h_per_9 * ip) / 9.0
                        projected_whip = (walks + estimated_hits) / ip
                projected_wins = calculate_weighted_projection('wins', {
                    'steamer': steamer.get('wins'),
                    'depthchart': depthchart.get('wins')
                })
                projected_saves = calculate_weighted_projection('saves', {
                    'steamer': steamer.get('saves'),
                    'depthchart': depthchart.get('saves')
                })
                # Quality Starts: Use DepthChart GS (has playing time) × QS rate
                # If DepthChart has QS, use weighted; otherwise use DepthChart GS-based estimate
                if depthchart.get('quality_starts') is not None:
                    projected_quality_starts = calculate_weighted_projection('quality_starts', {
                        'steamer': steamer.get('quality_starts'),
                        'depthchart': depthchart.get('quality_starts')
                    })
                    # Cap at realistic maximum (23 QS - even elite pitchers rarely exceed this)
                    if projected_quality_starts:
                        projected_quality_starts = min(projected_quality_starts, 23)
                        
                        # CRITICAL: Also cap based on IP (each QS requires at least 6 IP)
                        projected_ip = depthchart.get('innings_pitched') or steamer.get('innings_pitched')
                        if projected_ip and projected_ip > 0:
                            max_qs_from_ip = projected_ip / 6.0
                            projected_quality_starts = min(projected_quality_starts, max_qs_from_ip)
                else:
                    # Fallback: estimate from GS with realistic rates
                    gs = depthchart.get('games_started') or steamer.get('games_started')
                    era = depthchart.get('era') or steamer.get('era') or 4.0
                    if gs:
                        # More realistic QS rates based on actual data
                        if era < 3.00:
                            projected_quality_starts = min(gs * 0.65, 23)  # Elite: 65%, cap at 23
                        elif era < 3.50:
                            projected_quality_starts = min(gs * 0.58, 22)  # Very good: 58%, cap at 22
                        elif era < 4.00:
                            projected_quality_starts = min(gs * 0.50, 20)  # Good: 50%, cap at 20
                        elif era < 4.50:
                            projected_quality_starts = min(gs * 0.45, 18)  # Average: 45%, cap at 18
                        else:
                            projected_quality_starts = min(gs * 0.38, 16)  # Below average: 38%, cap at 16
                        
                        # CRITICAL: Cap QS based on IP (each QS requires at least 6 IP)
                        projected_ip = depthchart.get('innings_pitched') or steamer.get('innings_pitched')
                        if projected_ip and projected_ip > 0:
                            max_qs_from_ip = projected_ip / 6.0  # Each QS requires at least 6 IP
                            projected_quality_starts = min(projected_quality_starts, max_qs_from_ip)
                    else:
                        projected_quality_starts = steamer.get('quality_starts')
                        # Still apply IP cap if we have IP data
                        if projected_quality_starts:
                            projected_ip = depthchart.get('innings_pitched') or steamer.get('innings_pitched')
                            if projected_ip and projected_ip > 0:
                                max_qs_from_ip = projected_ip / 6.0
                                projected_quality_starts = min(projected_quality_starts, max_qs_from_ip)
            else:
                # Batting projections - use weighted averages
                projected_home_runs = calculate_weighted_projection('home_runs', {
                    'steamer': steamer.get('home_runs'),
                    'depthchart': depthchart.get('home_runs')
                })
                projected_runs = calculate_weighted_projection('runs', {
                    'steamer': steamer.get('runs'),
                    'depthchart': depthchart.get('runs')
                })
                projected_rbi = calculate_weighted_projection('rbi', {
                    'steamer': steamer.get('rbi'),
                    'depthchart': depthchart.get('rbi')
                })
                projected_stolen_bases = calculate_weighted_projection('stolen_bases', {
                    'steamer': steamer.get('stolen_bases'),
                    'depthchart': depthchart.get('stolen_bases')
                })
                projected_obp = calculate_weighted_projection('on_base_percentage', {
                    'steamer': steamer.get('on_base_percentage'),
                    'depthchart': depthchart.get('on_base_percentage')
                })
            
            # Get latest historical stats (2024 or 2025)
            historical_stats = player_data.get('historical_stats', {})
            latest_year = max([int(k) for k in historical_stats.keys() if k.isdigit()], default=None)
            
            # Statcast metrics from latest year
            statcast = {}
            if latest_year and str(latest_year) in historical_stats:
                year_data = historical_stats[str(latest_year)]
                statcast = year_data.get('statcast', {})
            
            # Park factors
            park_factors = player_data.get('park_factors', {}).get('2025', {})
            
            # Get innings pitched for pitchers
            projected_innings_pitched = None
            if is_pitcher:
                projected_innings_pitched = depthchart.get('innings_pitched') or steamer.get('innings_pitched')
            
            # Create Player object
            player = Player(
                player_id=player_id,
                name=name,
                position=position,
                team=team,
                adp=adp,
                drafted=False,
                
                # Projections (averaged across Steamer + DepthChart)
                projected_home_runs=projected_home_runs if not is_pitcher else None,
                projected_runs=projected_runs if not is_pitcher else None,
                projected_rbi=projected_rbi if not is_pitcher else None,
                projected_stolen_bases=projected_stolen_bases if not is_pitcher else None,
                projected_obp=projected_obp if not is_pitcher else None,
                projected_strikeouts=projected_strikeouts if is_pitcher else None,
                projected_era=projected_era if is_pitcher else None,
                projected_whip=projected_whip if is_pitcher else None,
                projected_wins=projected_wins if is_pitcher else None,
                projected_saves=projected_saves if is_pitcher else None,
                projected_quality_starts=self._apply_qs_ip_constraint(
                    projected_quality_starts, 
                    projected_innings_pitched
                ) if is_pitcher else None,
                projected_innings_pitched=projected_innings_pitched,
                
                # Statcast metrics
                savant_exit_velocity=statcast.get('exit_velocity_avg'),
                savant_launch_angle=statcast.get('launch_angle_avg'),
                savant_barrel_rate=statcast.get('barrel_rate'),
                savant_hard_hit_rate=statcast.get('hard_hit_percentage'),
                savant_xba=statcast.get('expected_batting_average'),
                savant_xslg=statcast.get('expected_slugging'),
                savant_xwoba=statcast.get('expected_woba'),
                savant_sprint_speed=statcast.get('sprint_speed'),
                
                # Park factors
                park_factor_offense=park_factors.get('park_factor'),
                park_factor_hr=park_factors.get('home_runs'),
                park_factor_pitching=park_factors.get('park_factor'),  # Same for pitchers
            )
            
            # Store full data in player for ML training (historical stats, etc.)
            # We'll add a method to extract these later
            player._master_dict_data = player_data  # Store for feature extraction
            
            return player
            
        except Exception as e:
            print(f"Error converting player {player_data.get('name', 'Unknown')}: {e}")
            return None
    
    @staticmethod
    def _average(values: List[Optional[float]]) -> Optional[float]:
        """Calculate average of non-None values."""
        valid_values = [v for v in values if v is not None]
        if not valid_values:
            return None
        return sum(valid_values) / len(valid_values)

