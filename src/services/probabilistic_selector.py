"""
Probabilistic player selection for auto-draft variability.

This module implements temperature-scaled softmax sampling for selecting players
from top candidates, with support for suboptimal pick injection.
"""

from typing import Dict, List, Tuple
import numpy as np

from src.models.player import Player
from src.services.variability_config import VariabilityConfig


class ProbabilisticSelector:
    """Implements probabilistic player selection with temperature scaling."""
    
    def __init__(self, config: VariabilityConfig, random_state: np.random.RandomState):
        """
        Initialize the probabilistic selector.
        
        Args:
            config: Variability configuration with temperature and mistake rate settings
            random_state: NumPy random state for reproducible randomness
        """
        self.config = config
        self.random_state = random_state
    
    def select_player(
        self,
        candidates: List[Dict],
        round_num: int,
        team_name: str
    ) -> Tuple[Player, str]:
        """
        Select a player from candidates using probabilistic selection.
        
        Args:
            candidates: List of dicts with keys: 'player', 'score', 'reasoning'
            round_num: Current draft round number
            team_name: Name of the team making the pick
        
        Returns:
            Tuple of (selected_player, reasoning)
        
        Raises:
            ValueError: If candidates list is empty
        """
        if not candidates:
            raise ValueError("No candidates provided")
        
        # Determine if this should be a suboptimal pick
        mistake_rate = self.config.get_mistake_rate_for_round(round_num)
        is_suboptimal = self.random_state.random() < mistake_rate
        
        if is_suboptimal:
            return self._select_suboptimal_player(candidates, round_num, team_name)
        else:
            return self._select_optimal_player(candidates, round_num, team_name)
    
    def _select_optimal_player(
        self,
        candidates: List[Dict],
        round_num: int,
        team_name: str
    ) -> Tuple[Player, str]:
        """
        Select from top N candidates using temperature-scaled softmax.
        
        Args:
            candidates: List of candidate dicts
            round_num: Current draft round number
            team_name: Name of the team making the pick
        
        Returns:
            Tuple of (selected_player, reasoning)
        """
        # Get top N candidates
        top_n = min(self.config.top_n_candidates, len(candidates))
        top_candidates = candidates[:top_n]
        
        # Extract scores
        scores = np.array([c['score'] for c in top_candidates])
        
        # Get temperature for this round
        temperature = self.config.get_temperature_for_round(round_num)
        
        # Apply temperature-scaled softmax
        probabilities = self._softmax_with_temperature(scores, temperature)
        
        # Sample based on probabilities
        selected_idx = self.random_state.choice(len(top_candidates), p=probabilities)
        selected = top_candidates[selected_idx]
        
        # Build reasoning
        reasoning = f"{selected['reasoning']} | Probabilistic selection (temp={temperature:.2f}, prob={probabilities[selected_idx]:.1%})"
        
        return selected['player'], reasoning
    
    def _select_suboptimal_player(
        self,
        candidates: List[Dict],
        round_num: int,
        team_name: str
    ) -> Tuple[Player, str]:
        """
        Select a suboptimal player from lower-ranked candidates.
        
        Args:
            candidates: List of candidate dicts
            round_num: Current draft round number
            team_name: Name of the team making the pick
        
        Returns:
            Tuple of (selected_player, reasoning)
        """
        min_rank, max_rank = self.config.suboptimal_range
        
        # Get candidates in the suboptimal range (convert to 0-indexed)
        suboptimal_candidates = candidates[min_rank-1:max_rank]
        
        if not suboptimal_candidates:
            # Fall back to optimal selection if no suboptimal candidates
            return self._select_optimal_player(candidates, round_num, team_name)
        
        # Uniform random selection from suboptimal range
        selected = self.random_state.choice(suboptimal_candidates)
        
        reasoning = f"{selected['reasoning']} | SUBOPTIMAL PICK (rank {min_rank}-{max_rank})"
        
        return selected['player'], reasoning
    
    def _softmax_with_temperature(self, scores: np.ndarray, temperature: float) -> np.ndarray:
        """
        Apply softmax with temperature scaling to scores.
        
        Temperature effects:
        - T → 0: Approaches argmax (deterministic, picks highest score)
        - T = 1: Standard softmax (moderate randomness)
        - T → ∞: Approaches uniform distribution (maximum randomness)
        
        Formula: P(i) = exp(score_i / T) / Σ exp(score_j / T)
        
        Args:
            scores: Array of candidate scores
            temperature: Temperature parameter (0.0 to 2.0)
        
        Returns:
            Array of probabilities that sum to 1.0
        """
        if temperature <= 0:
            # Deterministic: return one-hot for max score
            max_idx = np.argmax(scores)
            probs = np.zeros(len(scores))
            probs[max_idx] = 1.0
            return probs
        
        # Scale scores by temperature
        scaled_scores = scores / temperature
        
        # Subtract max for numerical stability
        scaled_scores = scaled_scores - np.max(scaled_scores)
        
        # Compute softmax
        exp_scores = np.exp(scaled_scores)
        probabilities = exp_scores / np.sum(exp_scores)
        
        return probabilities
