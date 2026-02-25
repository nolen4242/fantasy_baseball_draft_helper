# Design Document: Auto-Draft Variability

## Overview

This design introduces variability and randomness to the auto-draft system through probabilistic player selection, configurable drafter strategies, and controlled randomness. The system will transform the current deterministic auto-draft logic into a flexible framework that can simulate diverse drafting behaviors while maintaining reasonable draft quality.

The key innovation is using temperature-scaled softmax sampling to select from top candidates, combined with strategy profiles that adjust scoring weights, and occasional suboptimal picks to simulate human imperfection.

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Auto-Draft System                         │
│                                                              │
│  ┌────────────────┐      ┌──────────────────┐             │
│  │  Variability   │      │    Strategy      │             │
│  │  Config        │─────▶│    Manager       │             │
│  └────────────────┘      └──────────────────┘             │
│                                   │                         │
│                                   ▼                         │
│  ┌────────────────┐      ┌──────────────────┐             │
│  │  Random Seed   │      │   Probabilistic  │             │
│  │  Manager       │─────▶│   Selector       │             │
│  └────────────────┘      └──────────────────┘             │
│                                   │                         │
│                                   ▼                         │
│                          ┌──────────────────┐              │
│                          │  Recommendation  │              │
│                          │  Engine          │              │
│                          └──────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

1. **Variability Config**: Stores and manages all variability settings (temperature, mistake rate, strategy profiles)
2. **Strategy Manager**: Assigns strategies to teams and provides strategy-specific scoring weights
3. **Random Seed Manager**: Controls random number generation for reproducibility
4. **Probabilistic Selector**: Implements temperature-scaled softmax sampling and suboptimal pick injection
5. **Recommendation Engine**: Existing component that scores players (modified to accept strategy weights)

## Components and Interfaces

### 1. VariabilityConfig Class

```python
@dataclass
class VariabilityConfig:
    """Configuration for auto-draft variability."""
    
    # Global settings
    variability_enabled: bool = False
    random_seed: Optional[int] = None
    
    # Temperature settings (by round range)
    temperature_early_rounds: float = 0.3  # Rounds 1-5
    temperature_mid_rounds: float = 0.7    # Rounds 6-15
    temperature_late_rounds: float = 1.2   # Rounds 16+
    
    # Mistake rate settings (by round range)
    mistake_rate_early: float = 0.05   # 5% in rounds 1-5
    mistake_rate_mid: float = 0.10     # 10% in rounds 6-15
    mistake_rate_late: float = 0.15    # 15% in rounds 16+
    
    # Selection settings
    top_n_candidates: int = 5          # Number of top candidates to sample from
    suboptimal_range: Tuple[int, int] = (6, 15)  # Rank range for suboptimal picks
    
    # Strategy profiles
    strategy_profiles: Dict[str, StrategyProfile] = field(default_factory=dict)
    
    # Team strategy assignments
    team_strategies: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VariabilityConfig':
        """Deserialize from dictionary."""
        pass
    
    def save_to_file(self, filepath: str):
        """Save configuration to JSON file."""
        pass
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'VariabilityConfig':
        """Load configuration from JSON file."""
        pass
    
    def get_temperature_for_round(self, round_num: int) -> float:
        """Get temperature value for a specific round."""
        if round_num <= 5:
            return self.temperature_early_rounds
        elif round_num <= 15:
            return self.temperature_mid_rounds
        else:
            return self.temperature_late_rounds
    
    def get_mistake_rate_for_round(self, round_num: int) -> float:
        """Get mistake rate for a specific round."""
        if round_num <= 5:
            return self.mistake_rate_early
        elif round_num <= 15:
            return self.mistake_rate_mid
        else:
            return self.mistake_rate_late
```

### 2. StrategyProfile Class

```python
@dataclass
class StrategyProfile:
    """Defines a drafter strategy with custom scoring weights."""
    
    name: str
    description: str
    
    # Auto-draft scoring weights (must sum to 1.0)
    adp_weight: float = 0.60
    team_needs_weight: float = 0.30
    position_scarcity_weight: float = 0.10
    
    # Position preferences (multipliers applied to position scores)
    hitter_preference: float = 1.0
    pitcher_preference: float = 1.0
    
    # Specific position preferences
    catcher_preference: float = 1.0
    shortstop_preference: float = 1.0
    outfield_preference: float = 1.0
    
    # Category preferences (multipliers for category targeting)
    power_preference: float = 1.0      # HR, RBI
    speed_preference: float = 1.0      # SB
    average_preference: float = 1.0    # OBP
    strikeout_preference: float = 1.0  # K
    ratio_preference: float = 1.0      # ERA, WHIP
    wins_preference: float = 1.0       # W, QS
    saves_preference: float = 1.0      # SV, HLD
    
    def validate(self) -> List[str]:
        """Validate that weights sum to 1.0 and are in valid ranges."""
        errors = []
        
        weight_sum = self.adp_weight + self.team_needs_weight + self.position_scarcity_weight
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"Weights sum to {weight_sum:.2f}, must sum to 1.0")
        
        if not (0.0 <= self.adp_weight <= 1.0):
            errors.append("adp_weight must be between 0.0 and 1.0")
        
        # Check all preferences are positive
        for field_name in ['hitter_preference', 'pitcher_preference', 'power_preference', 
                          'speed_preference', 'average_preference']:
            value = getattr(self, field_name)
            if value < 0:
                errors.append(f"{field_name} must be non-negative")
        
        return errors

# Predefined strategy profiles
STRATEGY_PROFILES = {
    'balanced': StrategyProfile(
        name='balanced',
        description='Balanced approach following ADP with moderate team needs consideration',
        adp_weight=0.60,
        team_needs_weight=0.30,
        position_scarcity_weight=0.10
    ),
    
    'aggressive_hitters': StrategyProfile(
        name='aggressive_hitters',
        description='Prioritizes elite hitters and offensive categories',
        adp_weight=0.50,
        team_needs_weight=0.35,
        position_scarcity_weight=0.15,
        hitter_preference=1.3,
        pitcher_preference=0.7,
        power_preference=1.2,
        speed_preference=1.1
    ),
    
    'pitcher_heavy': StrategyProfile(
        name='pitcher_heavy',
        description='Emphasizes pitching depth and ratio categories',
        adp_weight=0.55,
        team_needs_weight=0.30,
        position_scarcity_weight=0.15,
        hitter_preference=0.8,
        pitcher_preference=1.4,
        strikeout_preference=1.2,
        ratio_preference=1.3,
        wins_preference=1.1
    ),
    
    'value_focused': StrategyProfile(
        name='value_focused',
        description='Strictly follows ADP value, less concerned with team needs',
        adp_weight=0.80,
        team_needs_weight=0.15,
        position_scarcity_weight=0.05
    ),
    
    'position_scarcity': StrategyProfile(
        name='position_scarcity',
        description='Prioritizes scarce positions like catcher and shortstop',
        adp_weight=0.45,
        team_needs_weight=0.30,
        position_scarcity_weight=0.25,
        catcher_preference=1.4,
        shortstop_preference=1.3
    )
}
```

### 3. StrategyManager Class

```python
class StrategyManager:
    """Manages strategy assignment and application for auto-drafted teams."""
    
    def __init__(self, config: VariabilityConfig, random_state: np.random.RandomState):
        self.config = config
        self.random_state = random_state
        self.team_strategies: Dict[str, StrategyProfile] = {}
    
    def assign_strategies_to_teams(self, team_names: List[str]):
        """Randomly assign strategies to teams at the start of a draft."""
        available_strategies = list(self.config.strategy_profiles.keys())
        
        for team_name in team_names:
            # Check if team already has assigned strategy in config
            if team_name in self.config.team_strategies:
                strategy_name = self.config.team_strategies[team_name]
            else:
                # Randomly assign a strategy
                strategy_name = self.random_state.choice(available_strategies)
            
            self.team_strategies[team_name] = self.config.strategy_profiles[strategy_name]
    
    def get_strategy_for_team(self, team_name: str) -> StrategyProfile:
        """Get the strategy profile for a specific team."""
        return self.team_strategies.get(team_name, STRATEGY_PROFILES['balanced'])
    
    def apply_strategy_to_scoring_config(
        self, 
        base_config: ScoringConfig, 
        strategy: StrategyProfile
    ) -> ScoringConfig:
        """Create a modified scoring config based on strategy preferences."""
        # Create a copy of the base config
        modified_config = ScoringConfig(**base_config.to_dict())
        
        # Apply strategy weights
        modified_config.autodraft_adp_weight = strategy.adp_weight
        modified_config.autodraft_team_needs_weight = strategy.team_needs_weight
        modified_config.autodraft_position_scarcity_weight = strategy.position_scarcity_weight
        
        # Apply position preferences by modifying position scarcity bonuses
        if strategy.hitter_preference != 1.0:
            # Adjust hitter-related bonuses
            modified_config.hitter_lineup_bonus_0_2 *= strategy.hitter_preference
            modified_config.hitter_lineup_bonus_3_5 *= strategy.hitter_preference
            modified_config.hitter_lineup_bonus_6_8 *= strategy.hitter_preference
        
        if strategy.pitcher_preference != 1.0:
            # Adjust pitcher-related bonuses
            modified_config.ip_accumulation_base_0_20 *= strategy.pitcher_preference
            modified_config.ip_accumulation_base_20_50 *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_high *= strategy.pitcher_preference
            modified_config.pitcher_scarcity_moderate *= strategy.pitcher_preference
        
        # Apply category preferences
        modified_config.category_weight_hr *= strategy.power_preference
        modified_config.category_weight_rbi *= strategy.power_preference
        modified_config.category_weight_sb *= strategy.speed_preference
        modified_config.category_weight_obp *= strategy.average_preference
        modified_config.category_weight_k *= strategy.strikeout_preference
        modified_config.category_weight_era *= strategy.ratio_preference
        modified_config.category_weight_whip *= strategy.ratio_preference
        modified_config.category_weight_wins *= strategy.wins_preference
        modified_config.category_weight_qs *= strategy.wins_preference
        modified_config.category_weight_saves *= strategy.saves_preference
        modified_config.category_weight_holds *= strategy.saves_preference
        
        return modified_config
```

### 4. ProbabilisticSelector Class

```python
class ProbabilisticSelector:
    """Implements probabilistic player selection with temperature scaling."""
    
    def __init__(self, config: VariabilityConfig, random_state: np.random.RandomState):
        self.config = config
        self.random_state = random_state
    
    def select_player(
        self,
        candidates: List[Dict],  # List of {player, score, reasoning}
        round_num: int,
        team_name: str
    ) -> Tuple[Player, str]:
        """
        Select a player from candidates using probabilistic selection.
        
        Returns: (selected_player, reasoning)
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
        """Select from top N candidates using temperature-scaled softmax."""
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
        """Select a suboptimal player from lower-ranked candidates."""
        min_rank, max_rank = self.config.suboptimal_range
        
        # Get candidates in the suboptimal range
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
```

### 5. Modified Auto-Draft Endpoint

```python
@app.route('/api/draft/auto-draft/pick', methods=['POST'])
def make_auto_draft_pick():
    """Make an auto-draft pick for a team using AI recommendations with variability."""
    try:
        # ... existing validation code ...
        
        # Check if variability is enabled
        variability_config = get_variability_config()  # Load from config file or use default
        
        if not variability_config.variability_enabled:
            # Use existing deterministic logic
            return _make_deterministic_pick(team_name, available, team_players, current_round, current_pick)
        
        # Use new probabilistic logic
        return _make_probabilistic_pick(
            team_name, 
            available, 
            team_players, 
            current_round, 
            current_pick,
            variability_config
        )
    
    except Exception as e:
        # ... error handling ...

def _make_probabilistic_pick(
    team_name: str,
    available: List[Player],
    team_players: List[Player],
    current_round: int,
    current_pick: int,
    variability_config: VariabilityConfig
) -> Response:
    """Make a probabilistic auto-draft pick using variability settings."""
    
    # Initialize random state
    random_state = get_random_state(variability_config)
    
    # Get strategy for this team
    strategy_manager = get_strategy_manager(variability_config, random_state)
    strategy = strategy_manager.get_strategy_for_team(team_name)
    
    # Apply strategy to scoring config
    base_config = recommendation_engine.get_config()
    modified_config = strategy_manager.apply_strategy_to_scoring_config(base_config, strategy)
    
    # Temporarily set the modified config
    original_config = recommendation_engine.config
    recommendation_engine.config = modified_config
    
    try:
        # Get recommendations using the recommendation engine
        recommendations = recommendation_engine.get_recommendations_for_team(
            available_players=available,
            team_players=team_players,
            draft_state=draft_service.current_draft,
            team_name=team_name,
            top_n=20,  # Get more candidates for probabilistic selection
            use_ml=False,  # Use rule-based for auto-draft
            is_auto_draft=True
        )
        
        if not recommendations:
            return jsonify({
                'success': False,
                'message': 'No valid recommendations available'
            }), 400
        
        # Use probabilistic selector to choose player
        selector = ProbabilisticSelector(variability_config, random_state)
        selected_player, reasoning = selector.select_player(
            recommendations,
            current_round,
            team_name
        )
        
        # Draft the selected player
        success = draft_service.draft_player(
            player_id=selected_player.player_id,
            team_name=team_name,
            player=selected_player
        )
        
        if success:
            # Log the pick for metrics
            log_auto_draft_pick(team_name, selected_player, strategy.name, current_round, reasoning)
            
            draft_dict = draft_service.current_draft.to_dict()
            return jsonify({
                'success': True,
                'draft': draft_dict,
                'picked_player': selected_player.to_dict(),
                'reasoning': f"[{strategy.name}] {reasoning}",
                'strategy': strategy.name,
                'draft_complete': draft_dict.get('is_complete', False)
            })
        
        return jsonify({
            'success': False,
            'message': 'Failed to draft player'
        }), 400
    
    finally:
        # Restore original config
        recommendation_engine.config = original_config
```

## Data Models

### Configuration File Format

```json
{
  "variability_enabled": true,
  "random_seed": 42,
  "temperature_early_rounds": 0.3,
  "temperature_mid_rounds": 0.7,
  "temperature_late_rounds": 1.2,
  "mistake_rate_early": 0.05,
  "mistake_rate_mid": 0.10,
  "mistake_rate_late": 0.15,
  "top_n_candidates": 5,
  "suboptimal_range": [6, 15],
  "strategy_profiles": {
    "balanced": {
      "name": "balanced",
      "description": "Balanced approach",
      "adp_weight": 0.60,
      "team_needs_weight": 0.30,
      "position_scarcity_weight": 0.10,
      "hitter_preference": 1.0,
      "pitcher_preference": 1.0
    }
  },
  "team_strategies": {
    "Team A": "aggressive_hitters",
    "Team B": "pitcher_heavy"
  }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Probability Distribution Validity

*For any* set of candidate scores and temperature value, the softmax function with temperature scaling should produce a valid probability distribution where all probabilities are non-negative, finite, and sum to 1.0 (within numerical tolerance).

**Validates: Requirements 1.5, 6.5**

### Property 2: Temperature Monotonicity

*For any* set of candidate scores, as temperature increases, the entropy of the probability distribution should increase (distribution becomes more uniform), and when temperature is 0.0, the highest-scored candidate should have probability 1.0.

**Validates: Requirements 6.2, 6.3, 6.4**

### Property 3: Top-N Candidate Selection

*For any* candidate list and configuration, when making an optimal pick, the selected player should always be from the top N candidates (where N is configurable).

**Validates: Requirements 1.4**

### Property 4: Probabilistic Selection Bias

*For any* candidate list with distinct scores, over many selections with the same temperature, higher-scored candidates should be selected more frequently than lower-scored candidates.

**Validates: Requirements 1.2**

### Property 5: Non-Determinism with Different Seeds

*For any* draft state, running the selection algorithm multiple times with different random seeds should produce different selections (with high probability).

**Validates: Requirements 1.3, 3.3**

### Property 6: Seed Reproducibility

*For any* draft state and random seed, running the probabilistic selector multiple times with the same seed should produce identical player selections.

**Validates: Requirements 3.2**

### Property 7: Strategy Weight Validity

*For any* strategy profile, the sum of adp_weight, team_needs_weight, and position_scarcity_weight must equal 1.0 (within tolerance of 0.01), and all weights must be non-negative.

**Validates: Requirements 2.5**

### Property 8: Strategy Assignment Completeness

*For any* list of team names, after strategy assignment, every team should have an assigned strategy profile.

**Validates: Requirements 2.2**

### Property 9: Strategy Application Consistency

*For any* base ScoringConfig and StrategyProfile, applying the strategy should modify the autodraft weights to match the strategy's weights, and should scale position/category preferences by the strategy's multipliers.

**Validates: Requirements 2.3**

### Property 10: Mistake Rate Frequency

*For any* round number and mistake rate, over many picks, the frequency of suboptimal picks should converge to the configured mistake rate for that round.

**Validates: Requirements 4.2**

### Property 11: Suboptimal Pick Range Validity

*For any* suboptimal pick, the selected player's rank must be within the configured suboptimal_range, and the player must satisfy roster constraints.

**Validates: Requirements 4.3, 4.4**

### Property 12: Round-Based Parameter Consistency

*For any* round number, the temperature and mistake rate returned should match the configured values for the appropriate round range (early: 1-5, mid: 6-15, late: 16+).

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

### Property 13: Configuration Serialization Round-Trip

*For any* valid VariabilityConfig object, serializing to JSON and then deserializing should produce an equivalent configuration with all fields preserved.

**Validates: Requirements 8.3**

### Property 14: Configuration Validation

*For any* configuration loaded from file, if any parameter is outside acceptable ranges, the validation should fail and report the specific errors.

**Validates: Requirements 8.4**

### Property 15: Backward Compatibility

*For any* draft state, when variability_enabled is false, the system should produce the same player selection as the original deterministic implementation.

**Validates: Requirements 10.2, 10.5**

## Error Handling

### Configuration Validation Errors

- **Invalid weight sums**: If strategy weights don't sum to 1.0, raise `ValueError` with descriptive message
- **Out of range values**: If temperature or mistake rate is outside valid range, raise `ValueError`
- **Missing strategy profile**: If team is assigned non-existent strategy, fall back to 'balanced' and log warning

### Selection Errors

- **Empty candidate list**: If no candidates provided to selector, raise `ValueError`
- **Invalid suboptimal range**: If suboptimal range exceeds candidate list size, fall back to optimal selection
- **Numerical instability**: If softmax computation encounters overflow, use log-space computation

### File I/O Errors

- **Missing config file**: If config file doesn't exist, create default configuration
- **Invalid JSON**: If config file is malformed, log error and use default configuration
- **Permission errors**: If cannot write config file, log error and continue with in-memory config

## Testing Strategy

### Unit Tests

Unit tests will focus on specific examples and edge cases:

1. **Softmax computation**: Test with known score arrays and verify probability outputs
2. **Temperature extremes**: Test T=0 (deterministic) and T=2 (high randomness)
3. **Strategy weight validation**: Test valid and invalid weight combinations
4. **Configuration serialization**: Test round-trip with various configurations
5. **Round-based parameter selection**: Test boundary conditions (rounds 5, 6, 15, 16)
6. **Suboptimal pick selection**: Test with various candidate list sizes
7. **Backward compatibility**: Test that deterministic mode matches original behavior

### Property-Based Tests

Property tests will verify universal correctness across all inputs:

1. **Probability distribution validity** (Property 1): Generate random scores and temperatures, verify probabilities sum to 1.0
2. **Temperature monotonicity** (Property 2): Verify that increasing temperature flattens distribution
3. **Strategy weight constraints** (Property 3): Generate random strategies, verify weights sum to 1.0
4. **Seed reproducibility** (Property 4): Run selection multiple times with same seed, verify identical results
5. **Mistake rate bounds** (Property 5): Generate random rounds, verify mistake rates are in valid range
6. **Candidate range validity** (Property 6): Generate random candidate lists, verify suboptimal picks are in range
7. **Configuration round-trip** (Property 7): Generate random configs, verify serialization preserves all fields
8. **Strategy application** (Property 8): Generate random strategies and configs, verify only specified fields change
9. **Backward compatibility** (Property 9): Generate random draft states, verify deterministic mode matches original
10. **Round-based consistency** (Property 10): Generate random rounds, verify temperature matches round range

### Integration Tests

1. **End-to-end draft simulation**: Run complete draft with variability enabled, verify all picks are valid
2. **Strategy diversity**: Run multiple drafts, verify different strategies produce different results
3. **Metrics collection**: Verify logging and metrics are collected correctly
4. **API compatibility**: Verify auto-draft endpoint works with both variability modes

### Testing Configuration

- Minimum 100 iterations per property test
- Each property test tagged with: **Feature: auto-draft-variability, Property N: [property text]**
- Use pytest for unit tests, Hypothesis for property-based tests
- Mock external dependencies (file I/O, random state) for deterministic testing
