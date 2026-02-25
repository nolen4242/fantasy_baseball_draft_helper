"""
Unit tests for ScoringBreakdown and FactorScore.
"""

import pytest
from src.services.scoring_breakdown import FactorScore, ScoringBreakdown


class TestFactorScore:
    """Test suite for FactorScore class."""
    
    def test_initialization(self):
        """Test that FactorScore initializes correctly."""
        factor = FactorScore(
            name="Standings Improvement",
            score=90.0,
            reasoning="Improves standings by 3.0 points",
            weight_used=30.0,
            raw_value=3.0
        )
        
        assert factor.name == "Standings Improvement"
        assert factor.score == 90.0
        assert factor.reasoning == "Improves standings by 3.0 points"
        assert factor.weight_used == 30.0
        assert factor.raw_value == 3.0
    
    def test_initialization_without_optional_fields(self):
        """Test that FactorScore works without optional fields."""
        factor = FactorScore(
            name="Team Needs",
            score=80.0,
            reasoning="Fills position need"
        )
        
        assert factor.name == "Team Needs"
        assert factor.score == 80.0
        assert factor.reasoning == "Fills position need"
        assert factor.weight_used is None
        assert factor.raw_value is None
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        factor = FactorScore(
            name="ML Model",
            score=165.0,
            reasoning="High predicted value",
            weight_used=3.0,
            raw_value=55.0
        )
        
        factor_dict = factor.to_dict()
        
        assert isinstance(factor_dict, dict)
        assert factor_dict['name'] == "ML Model"
        assert factor_dict['score'] == 165.0
        assert factor_dict['reasoning'] == "High predicted value"
        assert factor_dict['weight_used'] == 3.0
        assert factor_dict['raw_value'] == 55.0
    
    def test_to_dict_rounds_score(self):
        """Test that to_dict rounds score to 1 decimal place."""
        factor = FactorScore(
            name="Test",
            score=123.456789,
            reasoning="Test"
        )
        
        factor_dict = factor.to_dict()
        assert factor_dict['score'] == 123.5


class TestScoringBreakdown:
    """Test suite for ScoringBreakdown class."""
    
    def test_initialization(self):
        """Test that ScoringBreakdown initializes correctly."""
        factors = [
            FactorScore("Standings", 90.0, "Improves standings"),
            FactorScore("Roster Balance", 260.0, "Need hitters"),
            FactorScore("ML Model", 165.0, "High value")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="12345",
            player_name="Bobby Witt Jr",
            total_score=980.0,
            factors=factors,
            config_profile="default"
        )
        
        assert breakdown.player_id == "12345"
        assert breakdown.player_name == "Bobby Witt Jr"
        assert breakdown.total_score == 980.0
        assert len(breakdown.factors) == 3
        assert breakdown.config_profile == "default"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        factors = [
            FactorScore("Standings", 90.0, "Improves standings"),
            FactorScore("Team Needs", 80.0, "Fills need")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="12345",
            player_name="Test Player",
            total_score=500.0,
            factors=factors,
            config_profile="default"
        )
        
        breakdown_dict = breakdown.to_dict()
        
        assert isinstance(breakdown_dict, dict)
        assert breakdown_dict['player_id'] == "12345"
        assert breakdown_dict['player_name'] == "Test Player"
        assert breakdown_dict['total_score'] == 500.0
        assert len(breakdown_dict['factors']) == 2
        assert breakdown_dict['config_profile'] == "default"
        assert isinstance(breakdown_dict['factors'][0], dict)
    
    def test_get_top_factors_default(self):
        """Test getting top 3 factors by default."""
        factors = [
            FactorScore("Factor A", 50.0, "A"),
            FactorScore("Factor B", 200.0, "B"),
            FactorScore("Factor C", 30.0, "C"),
            FactorScore("Factor D", 150.0, "D"),
            FactorScore("Factor E", 10.0, "E")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=440.0,
            factors=factors,
            config_profile="default"
        )
        
        top_factors = breakdown.get_top_factors()
        
        assert len(top_factors) == 3
        assert top_factors[0].name == "Factor B"
        assert top_factors[1].name == "Factor D"
        assert top_factors[2].name == "Factor A"
    
    def test_get_top_factors_custom_n(self):
        """Test getting custom number of top factors."""
        factors = [
            FactorScore("Factor A", 50.0, "A"),
            FactorScore("Factor B", 200.0, "B"),
            FactorScore("Factor C", 30.0, "C")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=280.0,
            factors=factors,
            config_profile="default"
        )
        
        top_factors = breakdown.get_top_factors(2)
        
        assert len(top_factors) == 2
        assert top_factors[0].name == "Factor B"
        assert top_factors[1].name == "Factor A"
    
    def test_get_top_factors_with_negative_scores(self):
        """Test that top factors considers absolute values."""
        factors = [
            FactorScore("Positive", 50.0, "Positive"),
            FactorScore("Negative", -200.0, "Negative penalty"),
            FactorScore("Small", 10.0, "Small")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=-140.0,
            factors=factors,
            config_profile="default"
        )
        
        top_factors = breakdown.get_top_factors()
        
        assert len(top_factors) == 3
        assert top_factors[0].name == "Negative"  # Largest absolute value
        assert top_factors[1].name == "Positive"
        assert top_factors[2].name == "Small"
    
    def test_format_summary_basic(self):
        """Test basic summary formatting."""
        factors = [
            FactorScore("Standings", 90.0, "Improves standings by 3.0 points"),
            FactorScore("Roster Balance", 260.0, "Need hitters"),
            FactorScore("ML Model", 165.0, "High predicted value")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="12345",
            player_name="Bobby Witt Jr",
            total_score=515.0,
            factors=factors,
            config_profile="default"
        )
        
        summary = breakdown.format_summary()
        
        assert "Bobby Witt Jr" in summary
        assert "Total Score: 515" in summary
        assert "Score Breakdown:" in summary
        assert "Standings: +90.0" in summary
        assert "Roster Balance: +260.0" in summary
        assert "ML Model: +165.0" in summary
        assert "Top Factors:" in summary
    
    def test_format_summary_with_negative_scores(self):
        """Test summary formatting with negative scores."""
        factors = [
            FactorScore("Positive", 100.0, "Good"),
            FactorScore("Negative", -50.0, "Bad"),
            FactorScore("Zero", 0.0, "Neutral")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test Player",
            total_score=50.0,
            factors=factors,
            config_profile="default"
        )
        
        summary = breakdown.format_summary()
        
        assert "Positive: +100.0" in summary
        assert "Negative: -50.0" in summary
        # Zero scores should not appear in the breakdown section
        lines = summary.split('\n')
        breakdown_section = []
        in_breakdown = False
        for line in lines:
            if "Score Breakdown:" in line:
                in_breakdown = True
            elif "Top Factors:" in line:
                in_breakdown = False
            elif in_breakdown:
                breakdown_section.append(line)
        
        breakdown_text = '\n'.join(breakdown_section)
        assert "Zero" not in breakdown_text
    
    def test_format_summary_includes_reasoning(self):
        """Test that summary includes reasoning for factors."""
        factors = [
            FactorScore("Test Factor", 100.0, "This is the reasoning")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=100.0,
            factors=factors,
            config_profile="default"
        )
        
        summary = breakdown.format_summary()
        
        assert "This is the reasoning" in summary
        assert "→" in summary
    
    def test_format_summary_top_factors_section(self):
        """Test that top factors section is formatted correctly."""
        factors = [
            FactorScore("A", 10.0, "A"),
            FactorScore("B", 50.0, "B"),
            FactorScore("C", 30.0, "C")
        ]
        
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=90.0,
            factors=factors,
            config_profile="default"
        )
        
        summary = breakdown.format_summary()
        
        assert "Top Factors:" in summary
        assert "1. B: +50.0" in summary
        assert "2. C: +30.0" in summary
        assert "3. A: +10.0" in summary
    
    def test_empty_factors_list(self):
        """Test breakdown with no factors."""
        breakdown = ScoringBreakdown(
            player_id="1",
            player_name="Test",
            total_score=0.0,
            factors=[],
            config_profile="default"
        )
        
        summary = breakdown.format_summary()
        assert "Test" in summary
        assert "Total Score: 0" in summary
        
        top_factors = breakdown.get_top_factors()
        assert len(top_factors) == 0
