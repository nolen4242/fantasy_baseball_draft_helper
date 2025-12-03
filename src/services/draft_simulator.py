"""Draft simulator for generating training data."""
import random
from typing import List, Dict, Tuple
from src.models.player import Player
from src.models.draft import DraftState
from src.services.draft_order import DraftOrder


class DraftSimulator:
    """Simulates fantasy baseball drafts to generate training data."""
    
    def __init__(self, all_players: List[Player], total_teams: int = 13, roster_size: int = 21):
        self.all_players = all_players
        self.total_teams = total_teams
        self.roster_size = roster_size
        self.team_names = DraftOrder.get_all_teams()
    
    def simulate_draft(self, strategy: str = "adp") -> Dict:
        """
        Simulate a complete draft.
        
        Args:
            strategy: "adp" (follow ADP), "random" (random picks), "category" (category-need based)
        
        Returns:
            Dictionary with draft results:
            - team_rosters: Dict[team_name, List[Player]]
            - pick_history: List of (pick_number, team_name, player_id, round)
        """
        available_players = self.all_players.copy()
        team_rosters: Dict[str, List[Player]] = {name: [] for name in self.team_names}
        pick_history = []
        
        total_picks = self.total_teams * self.roster_size
        pick_number = 1
        
        for round_num in range(1, self.roster_size + 1):
            # Determine draft order for this round
            if round_num <= 5:
                # Rounds 1-5: fixed order
                round_order = self.team_names.copy()
            else:
                # Round 6+: snake draft
                snake_round = round_num - 5
                if snake_round % 2 == 1:
                    # Odd snake rounds: reverse order
                    round_order = list(reversed(self.team_names))
                else:
                    # Even snake rounds: normal order
                    round_order = self.team_names.copy()
            
            for team_name in round_order:
                if not available_players:
                    break
                
                # Select player based on strategy
                if strategy == "adp":
                    player = self._pick_by_adp(available_players, team_rosters[team_name])
                elif strategy == "random":
                    player = random.choice(available_players)
                elif strategy == "category":
                    player = self._pick_by_category_need(available_players, team_rosters[team_name])
                else:
                    player = self._pick_by_adp(available_players, team_rosters[team_name])
                
                # Draft the player
                team_rosters[team_name].append(player)
                available_players.remove(player)
                pick_history.append({
                    'pick_number': pick_number,
                    'round': round_num,
                    'team_name': team_name,
                    'player_id': player.player_id,
                    'player_name': player.name,
                    'position': player.position
                })
                pick_number += 1
        
        return {
            'team_rosters': team_rosters,
            'pick_history': pick_history
        }
    
    def _pick_by_adp(self, available: List[Player], my_roster: List[Player]) -> Player:
        """Pick best available player by ADP."""
        # Sort by ADP (lower is better, None goes to end)
        sorted_available = sorted(
            available,
            key=lambda p: (p.adp is None, p.adp or float('inf'))
        )
        return sorted_available[0]
    
    def _pick_by_category_need(self, available: List[Player], my_roster: List[Player]) -> Player:
        """Pick player that fills category needs."""
        # Calculate current category totals
        my_totals = self._calculate_category_totals(my_roster)
        
        # Score each available player
        best_player = None
        best_score = float('-inf')
        
        for player in available[:50]:  # Consider top 50 by ADP
            score = self._calculate_category_value(player, my_totals)
            if score > best_score:
                best_score = score
                best_player = player
        
        return best_player or available[0]
    
    def _calculate_category_totals(self, roster: List[Player]) -> Dict[str, float]:
        """Calculate total category stats for a roster."""
        totals = {
            'HR': 0.0, 'OBP': 0.0, 'R': 0.0, 'RBI': 0.0, 'SB': 0.0,
            'W': 0.0, 'QS': 0.0, 'K': 0.0, 'SV': 0.0, 'HD': 0.0,
            'ERA': 0.0, 'WHIP': 0.0, 'IP': 0.0
        }
        
        hitter_count = 0
        pitcher_count = 0
        
        for player in roster:
            is_hitter = player.position not in ['SP', 'RP', 'P']
            
            if is_hitter:
                hitter_count += 1
                totals['HR'] += player.projected_home_runs or 0
                totals['R'] += player.projected_runs or 0
                totals['RBI'] += player.projected_rbi or 0
                totals['SB'] += player.projected_stolen_bases or 0
                # OBP is averaged, not summed
                if player.projected_obp:
                    totals['OBP'] += player.projected_obp
            else:
                pitcher_count += 1
                totals['W'] += player.projected_wins or 0
                totals['QS'] += player.projected_quality_starts or 0
                totals['K'] += player.projected_strikeouts or 0
                totals['SV'] += player.projected_saves or 0
                totals['HD'] += player.projected_holds or 0
                # ERA and WHIP are averaged, not summed
                if player.projected_era:
                    totals['ERA'] += player.projected_era
                if player.projected_whip:
                    totals['WHIP'] += player.projected_whip
        
        # Average OBP, ERA, WHIP
        if hitter_count > 0:
            totals['OBP'] /= hitter_count
        if pitcher_count > 0:
            totals['ERA'] /= pitcher_count
            totals['WHIP'] /= pitcher_count
        
        return totals
    
    def _calculate_category_value(self, player: Player, my_totals: Dict[str, float]) -> float:
        """Calculate how much a player helps category totals."""
        value = 0.0
        is_hitter = player.position not in ['SP', 'RP', 'P']
        
        if is_hitter:
            # Weight categories based on typical scarcity
            value += (player.projected_home_runs or 0) * 2.5
            value += (player.projected_runs or 0) * 0.6
            value += (player.projected_rbi or 0) * 0.6
            value += (player.projected_stolen_bases or 0) * 3.5
            if player.projected_obp:
                value += (player.projected_obp - 0.300) * 500
        else:
            value += (player.projected_wins or 0) * 2.0
            value += (player.projected_quality_starts or 0) * 2.0
            value += (player.projected_strikeouts or 0) * 0.25
            value += (player.projected_saves or 0) * 3.0
            value += (player.projected_holds or 0) * 1.5
            if player.projected_era:
                value += max(0, (5.0 - player.projected_era) * 15)
            if player.projected_whip:
                value += max(0, (1.5 - player.projected_whip) * 30)
        
        return value

