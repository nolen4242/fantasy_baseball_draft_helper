"""Draft order management for Bob Uecker League."""
from typing import List


class DraftOrder:
    """Manages draft order for Bob Uecker League."""
    
    # Team order for rounds 1-4 (no snake)
    ROUNDS_1_4_ORDER = [
        "Runtime Terror",
        "Dawg",
        "Long Balls",
        "Simba's Dublin Green Sox",
        "Young Guns",
        "Gashouse Gang",
        "Magnum GI",
        "Trex",
        "Like a Nightmare",
        "Big Sticks",
        "MAGA DOGE",
        "Guillotine",
        "Rieken Havoc"
    ]
    
    # Starting round 5, it snakes (reverses each round)
    
    @classmethod
    def get_team_for_pick(cls, pick_number: int, total_teams: int = 13) -> str:
        """
        Get the team name for a given pick number.
        
        Args:
            pick_number: The pick number (1-indexed)
            total_teams: Total number of teams (default 13)
        
        Returns:
            Team name for that pick
        """
        round_number = ((pick_number - 1) // total_teams) + 1
        pick_in_round = ((pick_number - 1) % total_teams) + 1
        
        # Rounds 1-4: use standard order (NO snake)
        if round_number <= 4:
            return cls.ROUNDS_1_4_ORDER[pick_in_round - 1]
        
        # Round 5+: snake draft (alternate direction each round)
        # Round 5 is the first snake round (reversed)
        is_odd_snake_round = (round_number - 4) % 2 == 1  # Round 5 is "odd" in snake terms
        
        if is_odd_snake_round:
            # Odd snake rounds (5, 7, 9, etc.): reverse order (Rieken Havoc first)
            return cls.ROUNDS_1_4_ORDER[total_teams - pick_in_round]
        else:
            # Even snake rounds (6, 8, 10, etc.): normal order (Runtime Terror first)
            return cls.ROUNDS_1_4_ORDER[pick_in_round - 1]
    
    @classmethod
    def get_all_teams(cls) -> List[str]:
        """Get list of all team names."""
        return cls.ROUNDS_1_4_ORDER.copy()
    
    @classmethod
    def get_team_index(cls, team_name: str) -> int:
        """Get the index (0-based) of a team in the draft order."""
        try:
            return cls.ROUNDS_1_4_ORDER.index(team_name)
        except ValueError:
            return -1
    
    @classmethod
    def sanitize_team_name(cls, team_name: str) -> str:
        """Convert team name to folder-safe name."""
        return team_name.replace(" ", "_").replace("'", "").replace(".", "")

