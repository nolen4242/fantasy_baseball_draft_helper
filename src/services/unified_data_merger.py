"""Unified data merger that combines all data sources into Player objects."""
from typing import List, Dict, Optional
from pathlib import Path
from src.models.player import Player
from src.services.data_sources import (
    BaseballReferenceLoader, BaseballSavantLoader, FangraphsLoader,
    RotowireLoader, NFBCLoader, CBSLoader, BBForecasterLoader
)
from src.services.master_player_dict import MasterPlayerDict


class UnifiedDataMerger:
    """Merges data from all sources into unified Player objects."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
        self.data_dir = Path(data_dir)
        
        # Initialize loaders
        self.br_loader = BaseballReferenceLoader()
        self.savant_loader = BaseballSavantLoader()
        self.fg_loader = FangraphsLoader()
        self.rw_loader = RotowireLoader()
        self.nfbc_loader = NFBCLoader()
        self.cbs_loader = CBSLoader()
        self.bbf_loader = BBForecasterLoader()
        self.master_dict = MasterPlayerDict()
    
    def merge_all_sources(self, base_players: List[Player], year: int = 2025) -> List[Player]:
        """
        Merge all data sources into Player objects.
        
        Args:
            base_players: Base player list (from CBS or existing data)
            year: Year for projections (default 2025)
        
        Returns:
            List of Player objects with all data merged
        """
        # Load all data sources
        print("Loading Baseball Reference data...")
        br_standard = self.br_loader.load_standard_stats(year - 1, "batters")
        br_standard_p = self.br_loader.load_standard_stats(year - 1, "pitchers")
        br_advanced = self.br_loader.load_advanced_stats(year - 1, "batters")
        br_advanced_p = self.br_loader.load_advanced_stats(year - 1, "pitchers")
        br_proj = self.br_loader.load_projections(year, "batters")
        br_proj_p = self.br_loader.load_projections(year, "pitchers")
        
        print("Loading Baseball Savant data...")
        savant_batters = self.savant_loader.load_statcast(year - 1, "batters")
        savant_pitchers = self.savant_loader.load_statcast(year - 1, "pitchers")
        park_factors = self.savant_loader.load_park_factors(year - 1)
        
        print("Loading Fangraphs projections...")
        fg_steamer_b = self.fg_loader.load_projections("steamer", year, "batters")
        fg_steamer_p = self.fg_loader.load_projections("steamer", year, "pitchers")
        fg_zips_b = self.fg_loader.load_projections("zips", year, "batters")
        fg_zips_p = self.fg_loader.load_projections("zips", year, "pitchers")
        fg_thebat = self.fg_loader.load_projections("thebat", year, "batters")
        fg_atc_b = self.fg_loader.load_projections("atc", year, "batters")
        fg_atc_p = self.fg_loader.load_projections("atc", year, "pitchers")
        
        print("Loading Rotowire data...")
        rotowire_news = self.rw_loader.load_news(year)
        rotowire_injuries = self.rw_loader.load_injuries()
        
        print("Loading NFBC data...")
        nfbc_adp = self.nfbc_loader.load_adp(year)
        
        print("Loading CBS data...")
        cbs_positions = self.cbs_loader.load_position_eligibility(year)
        
        print("Loading BB Forecaster data...")
        bbf_predictions = self.bbf_loader.load_predictions(year)
        
        # Merge into players
        merged_players = []
        for player in base_players:
            normalized_name = self.br_loader.normalize_player_name(player.name)
            
            # Merge Baseball Reference
            if normalized_name in br_standard:
                stats = br_standard[normalized_name]
                player.br_runs = stats.get('runs')
                player.br_rbi = stats.get('rbi')
                player.br_home_runs = stats.get('home_runs')
                player.br_stolen_bases = stats.get('stolen_bases')
                player.br_hits = stats.get('hits')
                player.br_doubles = stats.get('doubles')
                player.br_triples = stats.get('triples')
                player.br_walks = stats.get('walks')
                player.br_strikeouts = stats.get('strikeouts')
                player.br_avg = stats.get('avg')
                player.br_slg = stats.get('slg')
                player.br_ops = stats.get('ops')
                player.br_mvps = stats.get('mvps')
                player.br_all_stars = stats.get('all_stars')
                player.br_gold_gloves = stats.get('gold_gloves')
            
            if normalized_name in br_standard_p:
                stats = br_standard_p[normalized_name]
                player.br_wins = stats.get('wins')
                player.br_losses = stats.get('losses')
                player.br_saves = stats.get('saves')
                player.br_innings_pitched = stats.get('innings_pitched')
                player.br_earned_runs = stats.get('earned_runs')
                player.br_cy_youngs = stats.get('cy_youngs')
            
            if normalized_name in br_advanced:
                adv = br_advanced[normalized_name]
                player.br_wrc_plus = adv.get('wrc_plus')
                player.br_ops_plus = adv.get('ops_plus')
                player.br_war = adv.get('war')
            
            if normalized_name in br_advanced_p:
                adv = br_advanced_p[normalized_name]
                player.br_era_plus = adv.get('era_plus')
                player.br_fip = adv.get('fip')
                player.br_xfip = adv.get('xfip')
                player.br_war = adv.get('war')
            
            if normalized_name in br_proj:
                proj = br_proj[normalized_name]
                player.br_proj_hr = proj.get('hr')
                player.br_proj_r = proj.get('r')
                player.br_proj_rbi = proj.get('rbi')
                player.br_proj_sb = proj.get('sb')
                player.br_proj_obp = proj.get('obp')
            
            if normalized_name in br_proj_p:
                proj = br_proj_p[normalized_name]
                player.br_proj_w = proj.get('w')
                player.br_proj_k = proj.get('k')
                player.br_proj_era = proj.get('era')
                player.br_proj_whip = proj.get('whip')
            
            # Merge Baseball Savant
            if normalized_name in savant_batters:
                sc = savant_batters[normalized_name]
                player.savant_exit_velocity = sc.get('exit_velocity')
                player.savant_launch_angle = sc.get('launch_angle')
                player.savant_barrel_rate = sc.get('barrel_rate')
                player.savant_hard_hit_rate = sc.get('hard_hit_rate')
                player.savant_xba = sc.get('xba')
                player.savant_xslg = sc.get('xslg')
                player.savant_xwoba = sc.get('xwoba')
                player.savant_sprint_speed = sc.get('sprint_speed')
                player.savant_defensive_runs = sc.get('defensive_runs')
            
            if normalized_name in savant_pitchers:
                sc = savant_pitchers[normalized_name]
                player.savant_spin_rate = sc.get('spin_rate')
                player.savant_velocity = sc.get('velocity')
            
            # Merge park factors
            if player.team and player.team.upper() in park_factors:
                pf = park_factors[player.team.upper()]
                player.park_factor_offense = pf.get('offense')
                player.park_factor_pitching = pf.get('pitching')
                player.park_factor_hr = pf.get('hr')
            
            # Merge Fangraphs projections
            if normalized_name in fg_steamer_b:
                proj = fg_steamer_b[normalized_name]
                player.fg_steamer_hr = proj.get('hr')
                player.fg_steamer_r = proj.get('r')
                player.fg_steamer_rbi = proj.get('rbi')
                player.fg_steamer_sb = proj.get('sb')
                player.fg_steamer_obp = proj.get('obp')
            
            if normalized_name in fg_steamer_p:
                proj = fg_steamer_p[normalized_name]
                player.fg_steamer_w = proj.get('w')
                player.fg_steamer_k = proj.get('k')
                player.fg_steamer_era = proj.get('era')
                player.fg_steamer_whip = proj.get('whip')
            
            if normalized_name in fg_zips_b:
                proj = fg_zips_b[normalized_name]
                player.fg_zips_hr = proj.get('hr')
                player.fg_zips_r = proj.get('r')
                player.fg_zips_rbi = proj.get('rbi')
                player.fg_zips_sb = proj.get('sb')
                player.fg_zips_obp = proj.get('obp')
            
            if normalized_name in fg_zips_p:
                proj = fg_zips_p[normalized_name]
                player.fg_zips_w = proj.get('w')
                player.fg_zips_k = proj.get('k')
                player.fg_zips_era = proj.get('era')
                player.fg_zips_whip = proj.get('whip')
            
            if normalized_name in fg_thebat:
                proj = fg_thebat[normalized_name]
                player.fg_thebat_hr = proj.get('hr')
                player.fg_thebat_r = proj.get('r')
                player.fg_thebat_rbi = proj.get('rbi')
                player.fg_thebat_sb = proj.get('sb')
                player.fg_thebat_obp = proj.get('obp')
            
            if normalized_name in fg_atc_b:
                proj = fg_atc_b[normalized_name]
                player.fg_atc_hr = proj.get('hr')
                player.fg_atc_r = proj.get('r')
                player.fg_atc_rbi = proj.get('rbi')
                player.fg_atc_sb = proj.get('sb')
                player.fg_atc_obp = proj.get('obp')
            
            if normalized_name in fg_atc_p:
                proj = fg_atc_p[normalized_name]
                player.fg_atc_w = proj.get('w')
                player.fg_atc_k = proj.get('k')
                player.fg_atc_era = proj.get('era')
                player.fg_atc_whip = proj.get('whip')
            
            # Merge Rotowire
            if normalized_name in rotowire_news:
                news = rotowire_news[normalized_name]
                player.news_items = news.get('items', [])
                player.news_sentiment = news.get('sentiment')
                player.contract_year = news.get('contract_year')
                player.big_contract = news.get('big_contract')
                player.prospect_called_up = news.get('prospect_called_up')
            
            if normalized_name in rotowire_injuries:
                inj = rotowire_injuries[normalized_name]
                player.injury_history = inj.get('history', [])
                player.injury_risk_score = inj.get('risk_score')
                player.current_injury = inj.get('current_injury')
            
            # Calculate sample size confidence and age decline
            player.sample_size_confidence = self._calculate_sample_size_confidence(player)
            player.age_decline_factor = self._calculate_age_decline(player)
            
            # Merge NFBC
            if normalized_name in nfbc_adp:
                adp_data = nfbc_adp[normalized_name]
                player.nfbc_adp = adp_data.get('adp')
                player.nfbc_adp_std_dev = adp_data.get('std_dev')
                # Use NFBC ADP as primary ADP if available
                if player.nfbc_adp and not player.adp:
                    player.adp = player.nfbc_adp
            
            # Merge CBS position eligibility
            if normalized_name in cbs_positions:
                player.position_eligibility = cbs_positions[normalized_name]
            
            # Merge BB Forecaster
            if normalized_name in bbf_predictions:
                player.bb_forecaster_prediction = bbf_predictions[normalized_name]
            
            merged_players.append(player)
        
        print(f"Merged data for {len(merged_players)} players")
        return merged_players
    
    def _calculate_sample_size_confidence(self, player: Player) -> float:
        """Calculate confidence in projections based on sample size."""
        # If player has historical stats, higher confidence
        has_history = (
            player.br_home_runs is not None or
            player.br_runs is not None or
            player.br_wins is not None
        )
        
        if not has_history:
            # Prospect or rookie - lower confidence
            return 0.3
        
        # More years of data = higher confidence
        # For now, simple heuristic
        if player.age and player.age < 25:
            return 0.6  # Young player, less history
        elif player.age and player.age > 30:
            return 0.9  # Veteran, lots of history
        else:
            return 0.8  # Prime age, good history
    
    def _calculate_age_decline_factor(self, player: Player) -> float:
        """Calculate age-based decline adjustment."""
        if not player.age:
            return 1.0
        
        # Age decline curves
        if player.age < 27:
            return 1.0  # Peak performance
        elif player.age < 30:
            return 0.98  # Slight decline
        elif player.age < 33:
            return 0.95  # Moderate decline
        elif player.age < 36:
            return 0.90  # Significant decline
        else:
            return 0.85  # Major decline

