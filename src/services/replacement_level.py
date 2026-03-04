"""Replacement-level analysis and Value Above Replacement (VAR) computation.

Determines the replacement-level baseline at each position and computes
how much better each player is compared to the last draftable player
at that position.
"""
from typing import Dict, List

from src.models.player import Player


class ReplacementLevelAnalyzer:
    """Determines replacement-level baselines and computes VAR."""

    # Number of roster slots per position across 13 teams
    POSITION_SLOTS = {
        'C': 13, '1B': 13, '2B': 13, '3B': 13, 'SS': 13,
        'MI': 13, 'CI': 13, 'OF': 52, 'U': 13, 'P': 117,
    }

    # Flex positions and which primary positions are eligible
    FLEX_ELIGIBLE = {
        'MI': {'2B', 'SS'},
        'CI': {'1B', '3B'},
        'U': {'C', '1B', '2B', '3B', 'SS', 'OF'},
    }

    PITCHER_POSITIONS = {'SP', 'RP', 'P'}

    def analyze(
        self, players: List[Player], zscores: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Compute Value Above Replacement for each player.

        Each player's VAR is calculated at every eligible position, and the
        position yielding the highest VAR is used.

        Args:
            players: List of Player instances (undrafted pool).
            zscores: Dict keyed by player_id -> {category: z_score, ..., 'composite': float}.

        Returns:
            Dict keyed by player_id -> VAR (float).
        """
        # Pre-compute replacement levels for each position
        replacement_levels: Dict[str, float] = {}
        for position in self.POSITION_SLOTS:
            eligible = [p for p in players if self._eligible_for_position(p, position)]
            replacement_levels[position] = self._replacement_level(
                position, eligible, zscores
            )

        # Compute VAR for each player using the best eligible position
        var_scores: Dict[str, float] = {}
        for player in players:
            if player.player_id not in zscores:
                var_scores[player.player_id] = 0.0
                continue

            composite = zscores[player.player_id].get('composite', 0.0)
            best_var = None

            for position in self.POSITION_SLOTS:
                if self._eligible_for_position(player, position):
                    var_at_pos = composite - replacement_levels[position]
                    if best_var is None or var_at_pos > best_var:
                        best_var = var_at_pos

            var_scores[player.player_id] = best_var if best_var is not None else 0.0

        return var_scores

    def _replacement_level(
        self,
        position: str,
        eligible_players: List[Player],
        zscores: Dict[str, Dict[str, float]],
    ) -> float:
        """Find the composite z-score of the replacement-level player.

        The replacement-level player is the one at the boundary of draftable
        supply — i.e., at index POSITION_SLOTS[position] (0-indexed) when
        players are sorted by composite z-score descending.

        Args:
            position: The roster position (e.g., 'C', 'OF', 'P').
            eligible_players: Players eligible for this position.
            zscores: Z-score dict keyed by player_id.

        Returns:
            The composite z-score of the replacement-level player.
            If fewer players than slots, returns the worst player's composite.
            If no players, returns 0.0.
        """
        # Filter to players that have z-scores
        scored = [
            p for p in eligible_players if p.player_id in zscores
        ]

        if not scored:
            return 0.0

        # Sort by composite z-score descending
        scored.sort(
            key=lambda p: zscores[p.player_id].get('composite', 0.0),
            reverse=True,
        )

        slots = self.POSITION_SLOTS[position]

        if len(scored) <= slots:
            # Fewer players than slots — use worst player's composite
            return zscores[scored[-1].player_id].get('composite', 0.0)

        # Replacement-level player is at the slot boundary (0-indexed)
        return zscores[scored[slots].player_id].get('composite', 0.0)

    def _eligible_for_position(self, player: Player, position: str) -> bool:
        """Check if a player can fill a given position slot.

        Rules:
            - Direct match: player.position == position
            - Pitcher flex: SP and RP are eligible for P
            - Flex positions: MI accepts 2B/SS, CI accepts 1B/3B,
              U accepts any hitter (C, 1B, 2B, 3B, SS, OF)

        Args:
            player: The Player instance.
            position: The roster position to check.

        Returns:
            True if the player can fill the position slot.
        """
        # Direct position match
        if player.position == position:
            return True

        # Pitcher flex: SP and RP can fill the P slot
        if position == 'P' and player.position in ('SP', 'RP'):
            return True

        # Flex position eligibility
        if position in self.FLEX_ELIGIBLE:
            return player.position in self.FLEX_ELIGIBLE[position]

        return False
