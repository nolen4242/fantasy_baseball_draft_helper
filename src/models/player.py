"""Player data model with comprehensive data sources."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class Player:
    """Represents a fantasy baseball player with comprehensive data."""
    player_id: str
    name: str
    position: str  # e.g., "OF", "1B", "SP", "RP"
    team: str
    age: Optional[int] = None
    
    # Projections - Bob Uecker League Categories
    # Batting: HR, OBP, R, RBI, SB
    projected_home_runs: Optional[float] = None
    projected_obp: Optional[float] = None  # On Base Percentage
    projected_runs: Optional[float] = None
    projected_rbi: Optional[float] = None
    projected_stolen_bases: Optional[float] = None
    # Pitching: ERA, K, SHOLDS (Saves + Holds x0.5), WHIP, WQS (Wins + Quality Starts)
    projected_wins: Optional[float] = None
    projected_quality_starts: Optional[float] = None  # QS
    projected_strikeouts: Optional[float] = None
    projected_era: Optional[float] = None
    projected_whip: Optional[float] = None
    projected_saves: Optional[float] = None
    projected_holds: Optional[float] = None
    
    # Draft status
    drafted: bool = False
    drafted_by_team: Optional[str] = None
    draft_round: Optional[int] = None
    draft_pick: Optional[int] = None
    
    # Average Draft Position
    adp: Optional[float] = None  # Average draft position (NFBC professional)
    
    # === NEW: Baseball Reference Data ===
    # Standard Stats (counting stats)
    br_runs: Optional[float] = None
    br_rbi: Optional[float] = None
    br_home_runs: Optional[float] = None
    br_stolen_bases: Optional[float] = None
    br_hits: Optional[float] = None
    br_doubles: Optional[float] = None
    br_triples: Optional[float] = None
    br_walks: Optional[float] = None
    br_strikeouts: Optional[float] = None
    br_avg: Optional[float] = None
    br_slg: Optional[float] = None
    br_ops: Optional[float] = None
    br_wins: Optional[float] = None
    br_losses: Optional[float] = None
    br_saves: Optional[float] = None
    br_innings_pitched: Optional[float] = None
    br_earned_runs: Optional[float] = None
    br_mvps: Optional[int] = None
    br_all_stars: Optional[int] = None
    br_gold_gloves: Optional[int] = None
    br_cy_youngs: Optional[int] = None
    
    # Advanced Stats
    br_wrc_plus: Optional[float] = None  # Weighted Runs Created Plus
    br_ops_plus: Optional[float] = None  # OPS Plus
    br_era_plus: Optional[float] = None  # ERA Plus
    br_fip: Optional[float] = None  # Fielding Independent Pitching
    br_xfip: Optional[float] = None  # Expected FIP
    br_war: Optional[float] = None  # Wins Above Replacement
    
    # BBRef Projections
    br_proj_hr: Optional[float] = None
    br_proj_r: Optional[float] = None
    br_proj_rbi: Optional[float] = None
    br_proj_sb: Optional[float] = None
    br_proj_obp: Optional[float] = None
    br_proj_w: Optional[float] = None
    br_proj_k: Optional[float] = None
    br_proj_era: Optional[float] = None
    br_proj_whip: Optional[float] = None
    
    # === NEW: Baseball Savant (Statcast) Data ===
    savant_exit_velocity: Optional[float] = None  # Average exit velocity
    savant_launch_angle: Optional[float] = None  # Average launch angle
    savant_barrel_rate: Optional[float] = None  # Barrel rate %
    savant_hard_hit_rate: Optional[float] = None  # Hard hit %
    savant_xba: Optional[float] = None  # Expected batting average
    savant_xslg: Optional[float] = None  # Expected slugging
    savant_xwoba: Optional[float] = None  # Expected wOBA
    savant_spin_rate: Optional[float] = None  # Average spin rate (pitchers)
    savant_velocity: Optional[float] = None  # Average velocity (pitchers)
    savant_sprint_speed: Optional[float] = None  # Sprint speed (batters)
    savant_defensive_runs: Optional[float] = None  # Defensive runs saved
    
    # Park Factors
    park_factor_offense: Optional[float] = None  # Home park offensive factor
    park_factor_pitching: Optional[float] = None  # Home park pitching factor
    park_factor_hr: Optional[float] = None  # Home park HR factor
    
    # === NEW: Fangraphs Projections ===
    fg_steamer_hr: Optional[float] = None
    fg_steamer_r: Optional[float] = None
    fg_steamer_rbi: Optional[float] = None
    fg_steamer_sb: Optional[float] = None
    fg_steamer_obp: Optional[float] = None
    fg_steamer_w: Optional[float] = None
    fg_steamer_k: Optional[float] = None
    fg_steamer_era: Optional[float] = None
    fg_steamer_whip: Optional[float] = None
    
    fg_zips_hr: Optional[float] = None
    fg_zips_r: Optional[float] = None
    fg_zips_rbi: Optional[float] = None
    fg_zips_sb: Optional[float] = None
    fg_zips_obp: Optional[float] = None
    fg_zips_w: Optional[float] = None
    fg_zips_k: Optional[float] = None
    fg_zips_era: Optional[float] = None
    fg_zips_whip: Optional[float] = None
    
    fg_thebat_hr: Optional[float] = None
    fg_thebat_r: Optional[float] = None
    fg_thebat_rbi: Optional[float] = None
    fg_thebat_sb: Optional[float] = None
    fg_thebat_obp: Optional[float] = None
    
    fg_atc_hr: Optional[float] = None  # Average of multiple systems
    fg_atc_r: Optional[float] = None
    fg_atc_rbi: Optional[float] = None
    fg_atc_sb: Optional[float] = None
    fg_atc_obp: Optional[float] = None
    fg_atc_w: Optional[float] = None
    fg_atc_k: Optional[float] = None
    fg_atc_era: Optional[float] = None
    fg_atc_whip: Optional[float] = None
    
    # === NEW: BB Forecaster ===
    bb_forecaster_prediction: Optional[float] = None  # Prediction market value
    
    # === NEW: Rotowire Data ===
    # News/Qualitative
    news_sentiment: Optional[float] = None  # -1 to 1 (negative to positive)
    news_items: List[str] = field(default_factory=list)  # Recent news items
    contract_year: Optional[bool] = None  # Is this a contract year?
    big_contract: Optional[bool] = None  # Just signed big contract?
    prospect_called_up: Optional[bool] = None  # Recently called up?
    
    # Injury/Risk
    injury_risk_score: Optional[float] = None  # 0-1 (0=low risk, 1=high risk)
    injury_history: List[str] = field(default_factory=list)  # Historical injuries
    current_injury: Optional[str] = None  # Current injury status
    sample_size_confidence: Optional[float] = None  # 0-1 (confidence in projections)
    age_decline_factor: Optional[float] = None  # Age-based decline adjustment
    
    # === NEW: NFBC Data ===
    nfbc_adp: Optional[float] = None  # Professional ADP
    nfbc_adp_std_dev: Optional[float] = None  # ADP standard deviation
    nfbc_historical_draft_pos: Optional[float] = None  # Historical average draft position
    
    # === NEW: CBS Data ===
    position_eligibility: List[str] = field(default_factory=list)  # All eligible positions
    cbs_historical_draft_pos: Optional[float] = None  # Historical CBS draft position
    value_per_pick: Optional[float] = None  # Historical value at this pick range
    
    def to_dict(self):
        """Convert player to dictionary."""
        return {
            'player_id': self.player_id,
            'name': self.name,
            'position': self.position,
            'team': self.team,
            'age': self.age,
            'projected_home_runs': self.projected_home_runs,
            'projected_obp': self.projected_obp,
            'projected_runs': self.projected_runs,
            'projected_rbi': self.projected_rbi,
            'projected_stolen_bases': self.projected_stolen_bases,
            'projected_wins': self.projected_wins,
            'projected_quality_starts': self.projected_quality_starts,
            'projected_strikeouts': self.projected_strikeouts,
            'projected_era': self.projected_era,
            'projected_whip': self.projected_whip,
            'projected_saves': self.projected_saves,
            'projected_holds': self.projected_holds,
            'drafted': self.drafted,
            'drafted_by_team': self.drafted_by_team,
            'draft_round': self.draft_round,
            'draft_pick': self.draft_pick,
            'adp': self.adp,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create player from dictionary."""
        return cls(**data)

