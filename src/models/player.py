"""Player data model."""
from dataclasses import dataclass, field
from typing import Optional


def validate_range(value: Optional[float], min_val: float, max_val: float, field_name: str) -> Optional[float]:
    """Validate that a value is within expected range."""
    if value is None:
        return None
    if value < min_val or value > max_val:
        # Log warning but don't fail - data might be unusual but valid
        pass  # Could add logging here
    return value


@dataclass
class Player:
    """Represents a fantasy baseball player."""
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
    projected_innings_pitched: Optional[float] = None  # For QS calculations
    
    # Draft status
    drafted: bool = False
    drafted_by_team: Optional[str] = None
    draft_round: Optional[int] = None
    draft_pick: Optional[int] = None
    
    # Average Draft Position
    adp: Optional[float] = None  # Average draft position
    
    # Statcast/Savant metrics - Hitters
    savant_exit_velocity: Optional[float] = None
    savant_launch_angle: Optional[float] = None
    savant_barrel_rate: Optional[float] = None
    savant_hard_hit_rate: Optional[float] = None
    savant_xba: Optional[float] = None  # Expected batting average
    savant_xslg: Optional[float] = None  # Expected slugging
    savant_xwoba: Optional[float] = None  # Expected wOBA
    savant_sprint_speed: Optional[float] = None
    
    # Statcast/Savant metrics - Pitchers
    savant_spin_rate: Optional[float] = None
    savant_velocity: Optional[float] = None
    
    # Park factors
    park_factor_offense: Optional[float] = None
    park_factor_hr: Optional[float] = None
    park_factor_pitching: Optional[float] = None
    
    # Risk assessment fields
    injury_risk_score: Optional[float] = None  # 0-1, higher = more risk
    current_injury: Optional[str] = None  # Current injury description
    sample_size_confidence: Optional[float] = None  # 0-1, higher = more confident
    age_decline_factor: Optional[float] = None  # Multiplier for age-related decline
    contract_year: bool = False  # True if player is in contract year
    
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
            'projected_innings_pitched': self.projected_innings_pitched,
            'drafted': self.drafted,
            'drafted_by_team': self.drafted_by_team,
            'draft_round': self.draft_round,
            'draft_pick': self.draft_pick,
            'adp': self.adp,
            'savant_exit_velocity': self.savant_exit_velocity,
            'savant_launch_angle': self.savant_launch_angle,
            'savant_barrel_rate': self.savant_barrel_rate,
            'savant_hard_hit_rate': self.savant_hard_hit_rate,
            'savant_xba': self.savant_xba,
            'savant_xslg': self.savant_xslg,
            'savant_xwoba': self.savant_xwoba,
            'savant_sprint_speed': self.savant_sprint_speed,
            'savant_spin_rate': self.savant_spin_rate,
            'savant_velocity': self.savant_velocity,
            'park_factor_offense': self.park_factor_offense,
            'park_factor_hr': self.park_factor_hr,
            'park_factor_pitching': self.park_factor_pitching,
            'injury_risk_score': self.injury_risk_score,
            'current_injury': self.current_injury,
            'sample_size_confidence': self.sample_size_confidence,
            'age_decline_factor': self.age_decline_factor,
            'contract_year': self.contract_year,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create player from dictionary, filtering out unknown fields."""
        # Get valid field names from the dataclass
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        # Filter data to only include valid fields
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def __post_init__(self):
        """Validate data after initialization."""
        # Ensure required fields are present
        if not self.player_id:
            raise ValueError("player_id is required")
        if not self.name:
            raise ValueError("name is required")
        
        # Normalize position
        if self.position:
            self.position = self.position.upper()
        
        # Ensure numeric fields are valid
        if self.adp is not None and self.adp < 0:
            self.adp = None
        
        # Clamp probability fields to 0-1 range
        if self.injury_risk_score is not None:
            self.injury_risk_score = max(0.0, min(1.0, self.injury_risk_score))
        if self.sample_size_confidence is not None:
            self.sample_size_confidence = max(0.0, min(1.0, self.sample_size_confidence))
        if self.age_decline_factor is not None:
            self.age_decline_factor = max(0.0, min(2.0, self.age_decline_factor))
    
    @property
    def is_pitcher(self) -> bool:
        """Check if player is a pitcher."""
        return self.position in ('SP', 'RP', 'P')
    
    @property
    def is_hitter(self) -> bool:
        """Check if player is a hitter."""
        return not self.is_pitcher

