"""Draft order management for Bob Uecker League."""
from typing import List


class DraftOrder:
    """Manages draft order for Bob Uecker League."""
    
    # Base draft order (Runtime Terror picks 1st)
    TEAM_ORDER = [
        "Runtime Terror",
        "Dawg",
        "Long Balls",
        "Simba's Dublin Green Sox",
        "Young Guns",
        "Gashouse Gang",
        "Magnum GI",
        "Trex",
        "Rieken Havoc",
        "Guillotine",
        "MAGA DOGE",
        "Big Sticks",
        "Like a Nightmare"
    ]

    # Rounds 1-4: fixed order. Round 5+: snake (direction flips each round).
    # Round 5 = first snake round (reverse), Round 6 = normal, Round 7 = reverse, etc.
    FIXED_ROUNDS = 4

    # Keep legacy alias so existing code that references ROUNDS_1_5_ORDER still works
    ROUNDS_1_5_ORDER = TEAM_ORDER

    @classmethod
    def get_team_for_pick(cls, pick_number: int, total_teams: int = 13) -> str:
        """Get the team name for a given pick number (1-indexed)."""
        round_number = ((pick_number - 1) // total_teams) + 1
        pick_in_round = ((pick_number - 1) % total_teams) + 1

        if round_number <= cls.FIXED_ROUNDS:
            return cls.TEAM_ORDER[pick_in_round - 1]

        # Snake rounds: first snake round is reverse, then alternates
        snake_index = round_number - cls.FIXED_ROUNDS  # 1-based
        if snake_index % 2 == 1:
            # Odd snake rounds (5, 7, 9, …): reverse order
            return cls.TEAM_ORDER[total_teams - pick_in_round]
        else:
            # Even snake rounds (6, 8, 10, …): normal order
            return cls.TEAM_ORDER[pick_in_round - 1]
    
    @classmethod
    def get_all_teams(cls) -> List[str]:
        """Get list of all team names."""
        return cls.ROUNDS_1_5_ORDER.copy()
    
    @classmethod
    def get_team_index(cls, team_name: str) -> int:
        """Get the index (0-based) of a team in the draft order."""
        try:
            return cls.ROUNDS_1_5_ORDER.index(team_name)
        except ValueError:
            return -1
    
    @classmethod
    def sanitize_team_name(cls, team_name: str) -> str:
        """Convert team name to folder-safe name."""
        return team_name.replace(" ", "_").replace("'", "").replace(".", "")

