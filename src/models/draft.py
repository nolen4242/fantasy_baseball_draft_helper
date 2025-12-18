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
        Note: This checks total player count, but teams may still need to fill specific positions.
        """
        # Check total picks - should be total_teams * roster_size
        total_expected_picks = self.total_teams * self.roster_size
        if len(self.picks) >= total_expected_picks:
            # Even if we have enough picks, allow drafting to continue if teams need positions
            # The draft can be "complete" but still allow position-filling picks
            return True
        
        # Also verify all teams have reached roster size (double-check)
        if self.team_rosters:
            for team_name, player_ids in self.team_rosters.items():
                if len(player_ids) < self.roster_size:
                    return False
            # If we get here, all teams are full
            return True
        
        return False
    
    def to_dict(self):
        """Convert draft state to dictionary."""
        # Update is_complete status
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

