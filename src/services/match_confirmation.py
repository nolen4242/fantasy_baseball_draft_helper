"""Match confirmation service for cross-database player matching."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from src.services.player_matcher import PlayerMatcher, MatchCandidate


class MatchConfirmationService:
    """
    Manages player match confirmations across databases.
    Stores confirmed matches and pending matches that need user confirmation.
    """
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data" / "processed"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.confirmed_matches_file = self.data_dir / "confirmed_matches.json"
        self.pending_matches_file = self.data_dir / "pending_matches.json"
        self.player_matcher = PlayerMatcher()
        
        # Load existing matches
        self.confirmed_matches = self._load_confirmed_matches()
        self.pending_matches = self._load_pending_matches()
    
    def _load_confirmed_matches(self) -> Dict[str, List[str]]:
        """Load confirmed player matches."""
        if not self.confirmed_matches_file.exists():
            return {}
        
        try:
            with open(self.confirmed_matches_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _load_pending_matches(self) -> Dict[str, List[Dict]]:
        """Load pending matches that need confirmation."""
        if not self.pending_matches_file.exists():
            return {}
        
        try:
            with open(self.pending_matches_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_confirmed_matches(self):
        """Save confirmed matches to file."""
        with open(self.confirmed_matches_file, 'w', encoding='utf-8') as f:
            json.dump(self.confirmed_matches, f, indent=2)
    
    def _save_pending_matches(self):
        """Save pending matches to file."""
        with open(self.pending_matches_file, 'w', encoding='utf-8') as f:
            json.dump(self.pending_matches, f, indent=2)
    
    def find_matches_needing_confirmation(
        self,
        players_by_source: Dict[str, List]
    ) -> Dict[str, List[Dict]]:
        """
        Find matches across databases that need confirmation.
        Only returns matches with confidence < 0.95 (high confidence matches are auto-confirmed).
        
        Args:
            players_by_source: Dict mapping source name to list of players
        
        Returns:
            Dict mapping player_id to list of potential matches
        """
        match_report = {}
        
        # Convert to dict format for matcher
        all_players_dict = []
        for source, players in players_by_source.items():
            for player in players:
                all_players_dict.append({
                    'player_id': getattr(player, 'player_id', ''),
                    'name': getattr(player, 'name', ''),
                    'source': source
                })
        
        # Find matches for each player
        for source, players in players_by_source.items():
            for player in players:
                player_id = getattr(player, 'player_id', '')
                player_name = getattr(player, 'name', '')
                
                # Skip if already confirmed
                if player_id in self.confirmed_matches:
                    continue
                
                # Find matches
                matches = self.player_matcher.find_matches(
                    player_name=player_name,
                    player_source=source,
                    candidate_players=all_players_dict,
                    min_confidence=0.70
                )
                
                # Filter: auto-confirm high confidence (>= 0.95), ask about medium (0.85-0.95), ignore low (< 0.85)
                needs_confirmation = []
                auto_confirmed = []
                
                for match in matches:
                    if match.confidence >= 0.95:
                        # Auto-confirm high confidence matches
                        auto_confirmed.append(match.player_id)
                    elif match.confidence >= 0.85:
                        # Need confirmation for medium confidence
                        needs_confirmation.append({
                            'player_id': match.player_id,
                            'name': match.name,
                            'source': match.source,
                            'confidence': match.confidence,
                            'reason': match.match_reason
                        })
                
                # Auto-confirm high confidence matches
                if auto_confirmed:
                    if player_id not in self.confirmed_matches:
                        self.confirmed_matches[player_id] = []
                    self.confirmed_matches[player_id].extend(auto_confirmed)
                    self._save_confirmed_matches()
                
                # Store pending matches
                if needs_confirmation:
                    match_report[player_id] = needs_confirmation
                    self.pending_matches[player_id] = needs_confirmation
        
        self._save_pending_matches()
        return match_report
    
    def confirm_match(self, player1_id: str, player2_id: str) -> bool:
        """
        Confirm that two players are the same person.
        
        Args:
            player1_id: ID of first player
            player2_id: ID of second player
        
        Returns:
            True if confirmed successfully
        """
        # Add to confirmed matches (bidirectional)
        if player1_id not in self.confirmed_matches:
            self.confirmed_matches[player1_id] = []
        if player2_id not in self.confirmed_matches:
            self.confirmed_matches[player2_id] = []
        
        if player2_id not in self.confirmed_matches[player1_id]:
            self.confirmed_matches[player1_id].append(player2_id)
        if player1_id not in self.confirmed_matches[player2_id]:
            self.confirmed_matches[player2_id].append(player1_id)
        
        # Remove from pending matches
        if player1_id in self.pending_matches:
            self.pending_matches[player1_id] = [
                m for m in self.pending_matches[player1_id]
                if m['player_id'] != player2_id
            ]
            if not self.pending_matches[player1_id]:
                del self.pending_matches[player1_id]
        
        if player2_id in self.pending_matches:
            self.pending_matches[player2_id] = [
                m for m in self.pending_matches[player2_id]
                if m['player_id'] != player1_id
            ]
            if not self.pending_matches[player2_id]:
                del self.pending_matches[player2_id]
        
        self._save_confirmed_matches()
        self._save_pending_matches()
        
        return True
    
    def reject_match(self, player1_id: str, player2_id: str) -> bool:
        """
        Reject a match (mark as not the same player).
        
        Args:
            player1_id: ID of first player
            player2_id: ID of second player
        
        Returns:
            True if rejected successfully
        """
        # Remove from pending matches
        if player1_id in self.pending_matches:
            self.pending_matches[player1_id] = [
                m for m in self.pending_matches[player1_id]
                if m['player_id'] != player2_id
            ]
            if not self.pending_matches[player1_id]:
                del self.pending_matches[player1_id]
        
        if player2_id in self.pending_matches:
            self.pending_matches[player2_id] = [
                m for m in self.pending_matches[player2_id]
                if m['player_id'] != player1_id
            ]
            if not self.pending_matches[player2_id]:
                del self.pending_matches[player2_id]
        
        self._save_pending_matches()
        return True
    
    def get_pending_matches(self) -> Dict[str, List[Dict]]:
        """Get all pending matches that need confirmation."""
        return self.pending_matches
    
    def get_confirmed_matches(self) -> Dict[str, List[str]]:
        """Get all confirmed matches."""
        return self.confirmed_matches
    
    def is_match_confirmed(self, player1_id: str, player2_id: str) -> bool:
        """Check if two players are confirmed as the same."""
        return (
            player1_id in self.confirmed_matches and
            player2_id in self.confirmed_matches[player1_id]
        )



