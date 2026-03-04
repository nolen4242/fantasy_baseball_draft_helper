"""Savant-informed player adjustment service.

Uses Statcast metrics (xwOBA, barrel rate, exit velocity, sprint speed) to
identify players whose projections may understate or overstate true talent,
flagging buy-low and sell-high candidates.
"""
from typing import Optional, Tuple

from src.models.player import Player


class SavantAdjuster:
    """Adjusts player scores using Statcast data."""

    # League-average baselines (approximate MLB averages)
    AVG_BARREL_RATE = 8.0
    AVG_EXIT_VELO = 88.5
    AVG_SPRINT_SPEED = 27.0  # ft/s
    AVG_XWOBA = 0.315

    # Thresholds
    XWOBA_GAP_THRESHOLD = 0.020  # Minimum gap to trigger buy-low/sell-high

    PITCHER_POSITIONS = {'SP', 'RP', 'P'}

    def adjust(self, player: Player, savant: Optional[dict]) -> Tuple[float, Optional[str]]:
        """Compute a Savant-based adjustment score and optional signal string.

        Args:
            player: The Player instance.
            savant: Dict of Statcast metrics for the player's most recent season,
                    or None if no Savant data is available.

        Returns:
            Tuple of (adjustment_score, signal_string_or_none).
            Returns (0.0, None) when savant data is None or missing key metrics.
        """
        if savant is None:
            return (0.0, None)

        # xwoba is the key metric — without it we can't compute the core adjustment
        if 'xwoba' not in savant or savant['xwoba'] is None:
            return (0.0, None)

        if player.position in self.PITCHER_POSITIONS:
            return self._pitcher_adjustment(player, savant)
        return self._hitter_adjustment(player, savant)

    def _hitter_adjustment(self, player: Player, savant: dict) -> Tuple[float, Optional[str]]:
        """Compute adjustment for a hitter based on Statcast metrics.

        Components:
        - xwOBA gap: compare xwOBA to projected OBP as proxy for actual performance
        - Power reliability: barrel rate + exit velocity above league average
        - Speed reliability: sprint speed above league average

        Args:
            player: The hitter Player instance.
            savant: Dict of Statcast metrics.

        Returns:
            Tuple of (total_adjustment, signal_string_or_none).
        """
        total = 0.0
        signal = None

        xwoba = savant['xwoba']

        # Use projected OBP as proxy for actual performance
        actual = player.projected_obp
        if actual is not None:
            gap = xwoba - actual
            if gap >= self.XWOBA_GAP_THRESHOLD:
                # Buy-low: xwOBA suggests player is better than projections
                total += min(gap * 10.0, 2.0)  # Cap at 2.0
                signal = f"Buy-low: xwOBA {xwoba:.3f} vs actual {actual:.3f}"
            elif gap <= -self.XWOBA_GAP_THRESHOLD:
                # Sell-high: xwOBA suggests player is worse than projections
                total += max(gap * 10.0, -2.0)  # Floor at -2.0
                signal = f"Sell-high: xwOBA {xwoba:.3f} vs actual {actual:.3f}"

        # Power reliability: above-average barrel rate + exit velocity
        barrel_rate = savant.get('barrel_rate')
        exit_velo = savant.get('exit_velo')
        if barrel_rate is not None and exit_velo is not None:
            if barrel_rate > self.AVG_BARREL_RATE and exit_velo > self.AVG_EXIT_VELO:
                # Both above average — power projections are reliable
                barrel_bonus = (barrel_rate - self.AVG_BARREL_RATE) * 0.05
                velo_bonus = (exit_velo - self.AVG_EXIT_VELO) * 0.05
                total += min(barrel_bonus + velo_bonus, 1.5)  # Cap power component

        # Speed reliability: above-average sprint speed
        sprint_speed = savant.get('sprint_speed')
        if sprint_speed is not None:
            if sprint_speed > self.AVG_SPRINT_SPEED:
                speed_bonus = (sprint_speed - self.AVG_SPRINT_SPEED) * 0.1
                total += min(speed_bonus, 1.0)  # Cap speed component

        return (total, signal)

    def _pitcher_adjustment(self, player: Player, savant: dict) -> Tuple[float, Optional[str]]:
        """Compute adjustment for a pitcher based on Statcast metrics.

        Uses xwOBA-against to assess whether the pitcher's ERA/WHIP projections
        are sustainable. Lower xwOBA-against means the pitcher is limiting
        contact quality effectively.

        Args:
            player: The pitcher Player instance.
            savant: Dict of Statcast metrics.

        Returns:
            Tuple of (total_adjustment, signal_string_or_none).
        """
        total = 0.0
        signal = None

        xwoba = savant['xwoba']  # xwOBA-against for pitchers
        threshold = 0.020

        if xwoba < self.AVG_XWOBA:
            # Pitcher limiting contact quality — positive adjustment
            gap = self.AVG_XWOBA - xwoba
            total += min(gap * 10.0, 2.0)  # Cap at 2.0
            if gap >= threshold:
                signal = f"Elite contact suppression: xwOBA-against {xwoba:.3f} vs avg {self.AVG_XWOBA:.3f}"
        elif xwoba > self.AVG_XWOBA + threshold:
            # Pitcher allowing hard contact — negative adjustment
            gap = xwoba - self.AVG_XWOBA
            total -= min(gap * 10.0, 2.0)  # Floor at -2.0
            signal = f"Contact concern: xwOBA-against {xwoba:.3f} vs avg {self.AVG_XWOBA:.3f}"

        return (total, signal)
