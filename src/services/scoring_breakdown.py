"""
Scoring breakdown classes for transparent recommendation scoring.

This module provides dataclasses to store and display detailed scoring breakdowns
for player recommendations.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FactorScore:
    """Individual scoring factor contribution."""
    name: str
    score: float
    reasoning: str
    weight_used: Optional[float] = None
    raw_value: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'score': round(self.score, 1),
            'reasoning': self.reasoning,
            'weight_used': self.weight_used,
            'raw_value': self.raw_value
        }


@dataclass
class ScoringBreakdown:
    """Complete breakdown of player scoring."""
    player_id: str
    player_name: str
    total_score: float
    factors: List[FactorScore]
    config_profile: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'player_id': self.player_id,
            'player_name': self.player_name,
            'total_score': round(self.total_score, 1),
            'factors': [f.to_dict() for f in self.factors],
            'config_profile': self.config_profile
        }
    
    def get_top_factors(self, n: int = 3) -> List[FactorScore]:
        """Get top N factors by absolute score contribution."""
        return sorted(self.factors, key=lambda f: abs(f.score), reverse=True)[:n]
    
    def format_summary(self) -> str:
        """Format a human-readable summary."""
        lines = [f"{self.player_name} - Total Score: {self.total_score:.0f}\n"]
        lines.append("Score Breakdown:")
        
        for factor in self.factors:
            if abs(factor.score) > 0.01:  # Exclude scores very close to zero
                sign = "+" if factor.score > 0 else ""
                lines.append(f"  {factor.name}: {sign}{factor.score:.1f}")
                if factor.reasoning:
                    lines.append(f"    → {factor.reasoning}")
        
        lines.append("\nTop Factors:")
        for i, factor in enumerate(self.get_top_factors(3), 1):
            lines.append(f"  {i}. {factor.name}: {factor.score:+.1f}")
        
        return "\n".join(lines)
