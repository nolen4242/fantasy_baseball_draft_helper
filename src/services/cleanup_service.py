"""Service for cleaning up test data and team rosters."""
import os
import shutil
from pathlib import Path
from typing import Optional
from src.services.draft_order import DraftOrder


class CleanupService:
    """Service for cleaning up team rosters and draft data after tests."""
    
    def __init__(self, teams_dir: Optional[str] = None, drafts_dir: Optional[str] = None):
        """
        Initialize cleanup service.
        
        Args:
            teams_dir: Directory containing team folders (default: data/teams)
            drafts_dir: Directory containing draft JSON files (default: same as teams_dir)
        """
        if teams_dir is None:
            project_root = Path(__file__).parent.parent.parent
            teams_dir = project_root / "data" / "teams"
        
        self.teams_dir = Path(teams_dir)
        self.drafts_dir = Path(drafts_dir) if drafts_dir else self.teams_dir
    
    def cleanup_all_team_rosters(self):
        """Remove all pick files and reset roster.json for all teams."""
        all_teams = DraftOrder.get_all_teams()
        
        for team_name in all_teams:
            self.cleanup_team_roster(team_name)
    
    def cleanup_team_roster(self, team_name: str):
        """
        Clean up a specific team's roster.
        
        Removes all pick files and resets roster.json to empty structure.
        Creates roster.json if it doesn't exist.
        """
        from src.services.team_service import TeamService
        import json
        
        team_service = TeamService()
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        
        # Create team directory if it doesn't exist
        team_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove all pick files
        for pick_file in team_dir.glob("pick_*.json"):
            pick_file.unlink()
        
        # Reset roster.json to empty structure (create if doesn't exist)
        roster_file = team_dir / "roster.json"
        empty_roster = {
            'team_name': team_name,
            'positions': team_service._get_empty_position_structure(),
            'all_players': []
        }
        with open(roster_file, 'w', encoding='utf-8') as f:
            json.dump(empty_roster, f, indent=2)
    
    def cleanup_all_drafts(self, keep_latest: bool = False):
        """
        Remove all draft JSON files.
        
        Args:
            keep_latest: If True, keep the most recent draft file
        """
        draft_files = list(self.drafts_dir.glob("draft_*.json"))
        
        if not draft_files:
            return
        
        if keep_latest:
            # Sort by modification time, keep the newest
            draft_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            draft_files = draft_files[1:]  # Skip the first (newest)
        
        for draft_file in draft_files:
            draft_file.unlink()
    
    def cleanup_everything(self, keep_latest_draft: bool = False):
        """
        Clean up all team rosters and draft files.
        
        Args:
            keep_latest_draft: If True, keep the most recent draft file
        """
        self.cleanup_all_team_rosters()
        self.cleanup_all_drafts(keep_latest=keep_latest_draft)
    
    def remove_team_folder(self, team_name: str):
        """Completely remove a team's folder and all its contents."""
        team_folder_name = DraftOrder.sanitize_team_name(team_name)
        team_dir = self.teams_dir / team_folder_name
        
        if team_dir.exists() and team_dir.is_dir():
            shutil.rmtree(team_dir)
    
    def remove_all_team_folders(self):
        """Completely remove all team folders."""
        all_teams = DraftOrder.get_all_teams()
        for team_name in all_teams:
            self.remove_team_folder(team_name)

