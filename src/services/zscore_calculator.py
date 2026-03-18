"""Z-score based player valuation calculator.

Computes per-category z-scores for all players relative to their position type
(hitter/pitcher), normalizing all categories to the same scale.
"""
from typing import Dict, List, Optional, Tuple

from src.models.player import Player


class ZScoreCalculator:
    """Computes z-scores for fantasy baseball scoring categories."""

    BATTING_CATEGORIES = ['HR', 'OBP', 'R', 'RBI', 'SB']
    PITCHING_CATEGORIES = ['ERA', 'K', 'SV', 'WHIP', 'WQS']
    INVERTED_CATEGORIES = {'ERA', 'WHIP'}  # lower is better

    PITCHER_POSITIONS = {'SP', 'RP', 'P'}

    def calculate(self, players: List[Player]) -> Dict[str, Dict[str, float]]:
        """Compute per-category z-scores and composite for each player.

        Args:
            players: List of Player instances with blended projections.

        Returns:
            Dict keyed by player_id -> {category: z_score, ..., 'composite': float}.
            Hitters get batting categories, pitchers get pitching categories.
            Returns empty dict for an empty player pool.
        """
        if not players:
            return {}

        hitters = [p for p in players if p.position not in self.PITCHER_POSITIONS]
        pitchers = [p for p in players if p.position in self.PITCHER_POSITIONS]

        result: Dict[str, Dict[str, float]] = {}

        # Compute stats and z-scores for hitters
        if hitters:
            batting_stats = self._compute_stats(hitters, self.BATTING_CATEGORIES)
            for player in hitters:
                scores: Dict[str, float] = {}
                composite = 0.0
                for cat in self.BATTING_CATEGORIES:
                    value = self._player_category_value(player, cat)
                    if value is not None and cat in batting_stats:
                        mean, std = batting_stats[cat]
                        z = self._zscore(value, mean, std, cat in self.INVERTED_CATEGORIES)
                    else:
                        z = 0.0
                    scores[cat] = z
                    composite += z
                scores['composite'] = composite
                result[player.player_id] = scores

        # Compute stats and z-scores for pitchers
        if pitchers:
            pitching_stats = self._compute_stats(pitchers, self.PITCHING_CATEGORIES)
            for player in pitchers:
                scores: Dict[str, float] = {}
                composite = 0.0
                for cat in self.PITCHING_CATEGORIES:
                    value = self._player_category_value(player, cat)
                    if value is not None and cat in pitching_stats:
                        mean, std = pitching_stats[cat]
                        z = self._zscore(value, mean, std, cat in self.INVERTED_CATEGORIES)
                    else:
                        z = 0.0
                    scores[cat] = z
                    composite += z
                scores['composite'] = composite
                result[player.player_id] = scores

        return result

    def _compute_stats(
        self, players: List[Player], categories: List[str]
    ) -> Dict[str, Tuple[float, float]]:
        """Compute mean and population stddev for each category.

        Only players with non-None values for a category are included in that
        category's mean/std calculation.

        Args:
            players: List of players (all hitters or all pitchers).
            categories: Category names to compute stats for.

        Returns:
            Dict mapping category name -> (mean, population_stddev).
            Categories where no player has a value are omitted.
        """
        stats: Dict[str, Tuple[float, float]] = {}
        for cat in categories:
            values = []
            for p in players:
                v = self._player_category_value(p, cat)
                if v is not None:
                    values.append(v)
            if not values:
                continue
            mean = sum(values) / len(values)
            # Population stddev (divide by N, not N-1)
            if len(values) < 2:
                std = 0.0
            else:
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                std = variance ** 0.5
            stats[cat] = (mean, std)
        return stats

    def _player_category_value(self, player: Player, category: str) -> Optional[float]:
        """Extract a player's raw value for a scoring category.

        Handles derived categories:
            SV = projected_saves
            WQS = projected_wins + projected_quality_starts

        Args:
            player: The Player instance.
            category: One of the BATTING_CATEGORIES or PITCHING_CATEGORIES.

        Returns:
            The raw float value, or None if the required projection fields are None.
        """
        category_map = {
            'HR': 'projected_home_runs',
            'OBP': 'projected_obp',
            'R': 'projected_runs',
            'RBI': 'projected_rbi',
            'SB': 'projected_stolen_bases',
            'ERA': 'projected_era',
            'K': 'projected_strikeouts',
            'WHIP': 'projected_whip',
        }

        if category == 'SV':
            return player.projected_saves

        if category == 'WQS':
            wins = player.projected_wins
            qs = player.projected_quality_starts
            if wins is None or qs is None:
                return None
            return wins + qs

        field = category_map.get(category)
        if field is None:
            return None
        return getattr(player, field, None)

    def _zscore(self, value: float, mean: float, std: float, inverted: bool) -> float:
        """Compute a z-score, with optional inversion for rate categories.

        For inverted categories (ERA, WHIP), a lower value is better, so the
        z-score sign is flipped: (mean - value) / std.

        Args:
            value: The player's raw category value.
            mean: The population mean for this category.
            std: The population standard deviation for this category.
            inverted: True for categories where lower is better (ERA, WHIP).

        Returns:
            The z-score as a float. Returns 0.0 if std is effectively zero.
        """
        if std < 1e-9:
            return 0.0
        if inverted:
            return (mean - value) / std
        return (value - mean) / std
