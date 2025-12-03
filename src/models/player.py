"""Player data model."""
from dataclasses import dataclass
from typing import Optional


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
    
    # Draft status
    drafted: bool = False
    drafted_by_team: Optional[str] = None
    draft_round: Optional[int] = None
    draft_pick: Optional[int] = None
    
    # Average Draft Position
    adp: Optional[float] = None  # Average draft position
    
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

