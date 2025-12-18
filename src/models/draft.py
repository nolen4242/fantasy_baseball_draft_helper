"""Draft state and team management."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class DraftPick:
    """Represents a single draft pick."""
    pick_number: int
    round: int
    team_name: str
    player_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DraftState:
    """Manages the overall draft state."""
    draft_id: str
    league_name: str
    total_teams: int
    roster_size: int
    my_team_name: str
    current_pick: int = 1
    current_round: int = 1
    picks: List[DraftPick] = field(default_factory=list)
    team_rosters: Dict[str, List[str]] = field(default_factory=dict)  # team_name -> [player_ids]
    is_complete: bool = False  # True when all teams have filled rosters
    
    def add_pick(self, pick: DraftPick):
        """Add a draft pick and update state."""
        self.picks.append(pick)
        if pick.team_name not in self.team_rosters:
            self.team_rosters[pick.team_name] = []
        self.team_rosters[pick.team_name].append(pick.player_id)
        
        # Update current pick/round
        self.current_pick += 1
        if self.current_pick > self.total_teams:
            self.current_round += 1
            self.current_pick = 1
    
    def get_my_roster(self) -> List[str]:
        """Get list of player IDs on my team."""
        return self.team_rosters.get(self.my_team_name, [])
    
    def get_drafted_players(self) -> List[str]:
        """Get all drafted player IDs."""
        return [pick.player_id for pick in self.picks]
    
    def is_draft_complete(self) -> bool:
        """
        Check if draft is complete (all teams have filled rosters AND all required positions).
        Verifies:
        1. All teams have roster_size players (21)
        2. All teams have all required positions filled
        3. Total picks equals total_teams * roster_size
        """
        from src.services.team_service import TeamService
        from src.services.draft_order import DraftOrder
        
        # First check: Total picks should equal total_teams * roster_size
        total_expected_picks = self.total_teams * self.roster_size
        if len(self.picks) < total_expected_picks:
            return False
        
        # Second check: All teams should have roster_size players
        if self.team_rosters:
            for team_name, player_ids in self.team_rosters.items():
                if len(player_ids) < self.roster_size:
                    return False
        
        # Third check: All teams have all required positions filled
        team_service = TeamService()
        required_positions = TeamService.POSITION_REQUIREMENTS
        all_teams = DraftOrder.get_all_teams()
        
        for team_name in all_teams:
            # Get team roster
            roster = team_service.get_team_roster(team_name)
            if not roster or 'positions' not in roster:
                return False  # Team doesn't have a roster structure
            
            positions = roster['positions']
            
            # Check each required position (excluding BENCH as it's optional)
            for pos, required_count in required_positions.items():
                if pos == 'BENCH':  # Skip bench - it's optional
                    continue
                
                # Count filled slots for this position
                filled_count = sum(1 for slot in positions.get(pos, []) if slot is not None)
                
                if filled_count < required_count:
                    return False  # Team is missing required position
        
        # All checks passed - draft is complete
        return True
    
    def to_dict(self):
        """Convert draft state to dictionary."""
        # Always re-check completion status before returning
        # This ensures is_complete reflects current position requirements
        self.is_complete = self.is_draft_complete()
        
        return {
            'draft_id': self.draft_id,
            'league_name': self.league_name,
            'total_teams': self.total_teams,
            'roster_size': self.roster_size,
            'my_team_name': self.my_team_name,
            'current_pick': self.current_pick,
            'current_round': self.current_round,
            'picks': [pick.__dict__ for pick in self.picks],
            'team_rosters': self.team_rosters,
            'is_complete': self.is_complete,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create draft state from dictionary."""
        picks = [DraftPick(**pick_data) for pick_data in data.get('picks', [])]
        draft = cls(
            draft_id=data['draft_id'],
            league_name=data['league_name'],
            total_teams=data['total_teams'],
            roster_size=data['roster_size'],
            my_team_name=data['my_team_name'],
            current_pick=data.get('current_pick', 1),
            current_round=data.get('current_round', 1),
            picks=picks,
            team_rosters=data.get('team_rosters', {}),
        )
        # Check completion status
        draft.is_complete = draft.is_draft_complete()
        return draft

