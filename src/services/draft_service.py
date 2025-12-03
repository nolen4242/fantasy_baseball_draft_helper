"""Service for managing draft state."""
import json
import os
from pathlib import Path
from typing import List, Optional
from src.models.draft import DraftState, DraftPick
from src.models.player import Player
from src.services.team_service import TeamService
from src.services.draft_order import DraftOrder


class DraftService:
    """Manages draft state and operations."""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Default to project root/data/teams
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data" / "teams"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.current_draft: Optional[DraftState] = None
        self.team_service = TeamService()
    
    def create_draft(
        self,
        draft_id: str,
        league_name: str,
        total_teams: int,
        roster_size: int,
        my_team_name: str
    ) -> DraftState:
        """Create a new draft."""
        # Initialize team rosters with all team names
        team_rosters = {}
        for team_name in DraftOrder.get_all_teams():
            team_rosters[team_name] = []
            # Initialize position-based roster structure for each team
            self.team_service.initialize_team_roster(team_name)
        
        draft = DraftState(
            draft_id=draft_id,
            league_name=league_name,
            total_teams=total_teams,
            roster_size=roster_size,
            my_team_name=my_team_name
        )
        draft.team_rosters = team_rosters
        self.current_draft = draft
        self.save_draft(draft)
        return draft
    
    def load_draft(self, draft_id: str) -> Optional[DraftState]:
        """Load a draft from file."""
        filepath = self.data_dir / f"{draft_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            draft = DraftState.from_dict(data)
            self.current_draft = draft
            return draft
    
    def save_draft(self, draft: DraftState):
        """Save draft state to file."""
        # Save to teams directory root
        filepath = self.data_dir / f"{draft.draft_id}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(draft.to_dict(), f, indent=2)
    
    def draft_player(
        self,
        player_id: str,
        team_name: str,
        player: Optional[Player] = None,
        draft: Optional[DraftState] = None
    ) -> bool:
        """Draft a player to a team."""
        if draft is None:
            draft = self.current_draft
        
        if draft is None:
            return False
        
        # Create pick
        pick = DraftPick(
            pick_number=len(draft.picks) + 1,
            round=draft.current_round,
            team_name=team_name,
            player_id=player_id
        )
        
        draft.add_pick(pick)
        self.save_draft(draft)
        
        # Save to team folder if we have player data
        if player:
            pick_info = {
                'pick_number': pick.pick_number,
                'round': pick.round,
                'team_name': team_name
            }
            self.team_service.save_team_pick(team_name, player, pick_info)
        
        return True
    
    def get_available_players(
        self,
        all_players: List[Player],
        draft: Optional[DraftState] = None
    ) -> List[Player]:
        """Get list of available (undrafted) players."""
        if draft is None:
            draft = self.current_draft
        
        if draft is None:
            return all_players
        
        drafted_ids = set(draft.get_drafted_players())
        return [p for p in all_players if p.player_id not in drafted_ids]
    
    def get_my_team_players(
        self,
        all_players: List[Player],
        draft: Optional[DraftState] = None
    ) -> List[Player]:
        """Get players on my team."""
        if draft is None:
            draft = self.current_draft
        
        if draft is None:
            return []
        
        my_player_ids = set(draft.get_my_roster())
        return [p for p in all_players if p.player_id in my_player_ids]
    
    def get_team_players(
        self,
        all_players: List[Player],
        team_name: str,
        draft: Optional[DraftState] = None
    ) -> List[Player]:
        """Get players on a specific team."""
        if draft is None:
            draft = self.current_draft
        
        if draft is None:
            return []
        
        team_player_ids = set(draft.team_rosters.get(team_name, []))
        return [p for p in all_players if p.player_id in team_player_ids]
    
    def revert_pick(self, pick_number: int, draft: Optional[DraftState] = None) -> bool:
        """Revert/undo a draft pick by pick number."""
        if draft is None:
            draft = self.current_draft
        
        if draft is None:
            return False
        
        # Find the pick to revert
        pick_to_revert = None
        pick_index = -1
        for i, pick in enumerate(draft.picks):
            if pick.pick_number == pick_number:
                pick_to_revert = pick
                pick_index = i
                break
        
        if pick_to_revert is None:
            return False
        
        # Remove from team roster
        if pick_to_revert.team_name in draft.team_rosters:
            if pick_to_revert.player_id in draft.team_rosters[pick_to_revert.team_name]:
                draft.team_rosters[pick_to_revert.team_name].remove(pick_to_revert.player_id)
        
        # Remove the pick from the list
        draft.picks.pop(pick_index)
        
        # Recalculate current pick and round
        if draft.picks:
            last_pick = draft.picks[-1]
            draft.current_pick = last_pick.pick_number + 1
            draft.current_round = last_pick.round
            # Check if we need to adjust round
            if draft.current_pick > draft.total_teams:
                draft.current_round += 1
                draft.current_pick = 1
        else:
            draft.current_pick = 1
            draft.current_round = 1
        
        # Remove from team folder
        self.team_service.remove_team_pick(pick_to_revert.team_name, pick_number)
        
        # Save updated draft
        self.save_draft(draft)
        
        return True

