"""Player matching service with intelligent name matching and cross-database matching."""
import re
import unicodedata
from typing import List, Dict, Tuple, Optional, Set
from difflib import SequenceMatcher
from dataclasses import dataclass


@dataclass
class MatchCandidate:
    """Represents a potential player match."""
    player_id: str
    name: str
    normalized_name: str
    source: str  # 'cbs', 'steamer', 'bbref', etc.
    confidence: float  # 0.0 to 1.0
    match_reason: str  # Why this is a match


class PlayerMatcher:
    """
    Intelligent player matching service.
    Handles name variations, duplicates, and cross-database matching.
    """
    
    def __init__(self):
        self.known_aliases = self._load_known_aliases()
        self.match_threshold_high = 0.95  # Very confident match
        self.match_threshold_medium = 0.85  # Likely match
        self.match_threshold_low = 0.70  # Possible match (needs confirmation)
    
    def normalize_player_name(self, name: str) -> str:
        """
        Normalize player name for matching.
        Handles:
        - Case insensitivity
        - Accents/diacritics
        - Suffixes (Jr., Sr., II, III, etc.)
        - Nicknames (Nate -> Nathan, etc.)
        - Punctuation removal
        """
        if not name:
            return ""
        
        # Remove accents/diacritics
        normalized = unicodedata.normalize('NFD', name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        
        # Convert to lowercase
        normalized = normalized.lower().strip()
        
        # Remove common suffixes
        normalized = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv|v|2nd|3rd|4th)$', '', normalized)
        
        # Remove punctuation
        normalized = normalized.replace(".", "").replace("'", "").replace("-", " ").replace(",", "")
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Apply known aliases (Nate -> Nathan, etc.)
        for alias, canonical in self.known_aliases.items():
            if normalized == alias.lower():
                normalized = canonical.lower()
                break
        
        return normalized
    
    def _load_known_aliases(self) -> Dict[str, str]:
        """Load known name aliases and nicknames."""
        return {
            'nate': 'nathan',
            'nate pearson': 'nathan pearson',
            'nate lowe': 'nathaniel lowe',
            'nate eovaldi': 'nathan eovaldi',
            'mike': 'michael',
            'mike trout': 'michael trout',
            'mike yastrzemski': 'michael yastrzemski',
            'jimmy': 'james',
            'jimmy rollins': 'james rollins',
            'jimmy nelson': 'james nelson',
            'chris': 'christopher',
            'chris sale': 'christopher sale',
            'chris paddack': 'christopher paddack',
            'chris taylor': 'christopher taylor',
            'joe': 'joseph',
            'joe ryan': 'joseph ryan',
            'joe musgrove': 'joseph musgrove',
            'tom': 'thomas',
            'tommy': 'thomas',
            'tommy edman': 'thomas edman',
            'tommy pham': 'thomas pham',
            'alex': 'alexander',
            'alex bregman': 'alexander bregman',
            'alex verdugo': 'alexander verdugo',
            'andy': 'andrew',
            'andy pages': 'andrew pages',
            'andy ibanez': 'andrew ibanez',
            'dave': 'david',
            'dave robertson': 'david robertson',
            'dave dahl': 'david dahl',
            'dan': 'daniel',
            'dan vogelbach': 'daniel vogelbach',
            'dan uggla': 'daniel uggla',
            'eddie': 'edward',
            'eddie rosario': 'edward rosario',
            'eddie julian': 'edward julian',
            'frankie': 'francis',
            'frankie montas': 'francis montas',
            'frankie lindor': 'francis lindor',
            'jake': 'jacob',
            'jake cronenworth': 'jacob cronenworth',
            'jake fraley': 'jacob fraley',
            'josh': 'joshua',
            'josh bell': 'joshua bell',
            'josh donaldson': 'joshua donaldson',
            'matt': 'matthew',
            'matt olson': 'matthew olson',
            'matt carpenter': 'matthew carpenter',
            'nick': 'nicholas',
            'nick castellanos': 'nicholas castellanos',
            'nick senzel': 'nicholas senzel',
            'rob': 'robert',
            'rob refsnyder': 'robert refsnyder',
            'rob cano': 'robert cano',
            'steve': 'steven',
            'steve cohen': 'steven cohen',
            'steve pearce': 'steven pearce',
            'will': 'william',
            'will smith': 'william smith',
            'will myers': 'william myers',
        }
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names (0.0 to 1.0).
        Uses multiple strategies for better matching.
        """
        norm1 = self.normalize_player_name(name1)
        norm2 = self.normalize_player_name(name2)
        
        if norm1 == norm2:
            return 1.0
        
        # Exact match after normalization
        if norm1 == norm2:
            return 1.0
        
        # Sequence similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Check if one name contains the other (partial match)
        if norm1 in norm2 or norm2 in norm1:
            # Boost similarity for partial matches
            similarity = max(similarity, 0.85)
        
        # Check for common first/last name swaps
        parts1 = norm1.split()
        parts2 = norm2.split()
        if len(parts1) == 2 and len(parts2) == 2:
            # Check if names are swapped
            if parts1[0] == parts2[1] and parts1[1] == parts2[0]:
                similarity = max(similarity, 0.90)
        
        return similarity
    
    def find_matches(
        self,
        player_name: str,
        player_source: str,
        candidate_players: List[Dict],
        min_confidence: float = 0.70
    ) -> List[MatchCandidate]:
        """
        Find potential matches for a player across databases.
        
        Args:
            player_name: Name of player to match
            player_source: Source of the player ('cbs', 'steamer', etc.)
            candidate_players: List of candidate players to match against
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of MatchCandidate objects sorted by confidence
        """
        normalized_target = self.normalize_player_name(player_name)
        matches = []
        
        for candidate in candidate_players:
            candidate_name = candidate.get('name', '')
            candidate_source = candidate.get('source', '')
            candidate_id = candidate.get('player_id', '')
            
            # Skip if same source (don't match within same database)
            if candidate_source == player_source:
                continue
            
            # Calculate similarity
            similarity = self.calculate_name_similarity(player_name, candidate_name)
            
            if similarity >= min_confidence:
                # Determine match reason
                if similarity >= 0.95:
                    reason = "Exact or near-exact name match"
                elif similarity >= 0.85:
                    reason = "High similarity match"
                else:
                    reason = "Possible match (needs confirmation)"
                
                matches.append(MatchCandidate(
                    player_id=candidate_id,
                    name=candidate_name,
                    normalized_name=self.normalize_player_name(candidate_name),
                    source=candidate_source,
                    confidence=similarity,
                    match_reason=reason
                ))
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        return matches
    
    def merge_duplicate_players(
        self,
        players: List[Dict],
        source: str = 'cbs'
    ) -> List[Dict]:
        """
        Merge duplicate players from the same source (e.g., same player in multiple position files).
        
        Args:
            players: List of player dictionaries
            source: Source identifier
        
        Returns:
            List of merged players (no duplicates)
        """
        # Group by normalized name
        player_groups: Dict[str, List[Dict]] = {}
        
        for player in players:
            name = player.get('name', '')
            normalized = self.normalize_player_name(name)
            
            if normalized not in player_groups:
                player_groups[normalized] = []
            player_groups[normalized].append(player)
        
        # Merge players with same normalized name
        merged_players = []
        
        for normalized_name, group in player_groups.items():
            if len(group) == 1:
                # No duplicates, add as-is
                merged_players.append(group[0])
            else:
                # Merge duplicates
                merged = self._merge_player_group(group, source)
                merged_players.append(merged)
        
        return merged_players
    
    def _merge_player_group(self, players: List[Dict], source: str) -> Dict:
        """
        Merge a group of duplicate players into one.
        Combines position eligibility and takes best available data.
        """
        if not players:
            return {}
        
        # Start with first player as base
        merged = players[0].copy()
        
        # Collect all positions
        positions = set()
        if 'position' in merged:
            positions.add(merged['position'])
        if 'position_eligibility' in merged:
            positions.update(merged['position_eligibility'])
        
        # Add positions from other players
        for player in players[1:]:
            if 'position' in player:
                positions.add(player['position'])
            if 'position_eligibility' in player:
                positions.update(player['position_eligibility'])
        
        # Update position eligibility
        merged['position_eligibility'] = sorted(list(positions))
        
        # If multiple positions, set primary position (prefer non-flexible)
        primary_positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP']
        for pos in primary_positions:
            if pos in positions:
                merged['position'] = pos
                break
        else:
            # No primary position found, use first available
            merged['position'] = sorted(list(positions))[0] if positions else 'U'
        
        # Merge stats (take non-null values, prefer first player's data)
        for player in players[1:]:
            for key, value in player.items():
                if key not in ['name', 'position', 'position_eligibility', 'player_id']:
                    if key not in merged or merged[key] is None:
                        merged[key] = value
        
        # Add metadata
        merged['_merged_from'] = len(players)
        merged['_source'] = source
        
        return merged
    
    def create_match_report(
        self,
        players_by_source: Dict[str, List[Dict]]
    ) -> Dict[str, List[MatchCandidate]]:
        """
        Create a report of potential matches across all sources.
        Returns matches that need confirmation.
        
        Args:
            players_by_source: Dict mapping source name to list of players
        
        Returns:
            Dict mapping player_id to list of potential matches
        """
        match_report = {}
        
        # Get all players with their source
        all_players = []
        for source, players in players_by_source.items():
            for player in players:
                all_players.append({
                    'player_id': player.get('player_id', ''),
                    'name': player.get('name', ''),
                    'source': source
                })
        
        # Find matches for each player
        for source, players in players_by_source.items():
            for player in players:
                player_name = player.get('name', '')
                player_id = player.get('player_id', '')
                
                # Find matches in other sources
                matches = self.find_matches(
                    player_name=player_name,
                    player_source=source,
                    candidate_players=all_players,
                    min_confidence=0.70  # Include all possible matches
                )
                
                # Only include matches that need confirmation (confidence < 0.95)
                needs_confirmation = [m for m in matches if m.confidence < 0.95]
                
                if needs_confirmation:
                    match_report[player_id] = needs_confirmation
        
        return match_report
    
    def confirm_match(
        self,
        player1_id: str,
        player2_id: str,
        players_by_source: Dict[str, List[Dict]]
    ) -> bool:
        """
        Confirm that two players are the same person.
        This should be called after user confirmation.
        
        Args:
            player1_id: ID of first player
            player2_id: ID of second player
            players_by_source: All players by source
        
        Returns:
            True if match confirmed, False otherwise
        """
        # Find both players
        player1 = None
        player2 = None
        
        for source, players in players_by_source.items():
            for player in players:
                if player.get('player_id') == player1_id:
                    player1 = player
                if player.get('player_id') == player2_id:
                    player2 = player
        
        if not player1 or not player2:
            return False
        
        # Merge the players
        # This would be implemented based on your merge strategy
        # For now, return True to indicate confirmation
        return True

