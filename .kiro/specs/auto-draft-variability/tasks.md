# Implementation Plan: Auto-Draft Variability

## Overview

This implementation adds variability and randomness to the auto-draft system through probabilistic player selection, configurable drafter strategies, and controlled randomness. The implementation will be done incrementally, starting with core data structures, then probabilistic selection logic, strategy management, and finally integration with the existing auto-draft endpoint.

## Tasks

- [x] 1. Create core data structures and configuration classes
  - [x] 1.1 Create StrategyProfile dataclass
    - Define StrategyProfile with all weight and preference fields
    - Implement validate() method to check weight sums and ranges
    - Create STRATEGY_PROFILES dictionary with 5 predefined strategies
    - _Requirements: 2.1, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 1.2 Write property test for StrategyProfile validation
    - **Property 7: Strategy Weight Validity**
    - **Validates: Requirements 2.5**
  
  - [x] 1.3 Create VariabilityConfig dataclass
    - Define VariabilityConfig with all configuration fields
    - Implement get_temperature_for_round() method
    - Implement get_mistake_rate_for_round() method
    - Implement to_dict() and from_dict() methods
    - Implement save_to_file() and load_from_file() methods
    - _Requirements: 3.1, 4.1, 6.1, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 10.1_
  
  - [x] 1.4 Write property test for round-based parameter selection
    - **Property 12: Round-Based Parameter Consistency**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
  
  - [x] 1.5 Write property test for configuration serialization
    - **Property 13: Configuration Serialization Round-Trip**
    - **Validates: Requirements 8.3**
  
  - [x] 1.6 Write property test for configuration validation
    - **Property 14: Configuration Validation**
    - **Validates: Requirements 8.4**

- [x] 2. Implement probabilistic selection logic
  - [x] 2.1 Create ProbabilisticSelector class
    - Implement __init__ with config and random_state parameters
    - Implement select_player() method with mistake rate logic
    - Implement _select_optimal_player() method
    - Implement _select_suboptimal_player() method
    - Implement _softmax_with_temperature() method
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.2, 4.3, 4.4, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 2.2 Write property test for softmax probability distribution
    - **Property 1: Probability Distribution Validity**
    - **Validates: Requirements 1.5, 6.5**
  
  - [x] 2.3 Write property test for temperature monotonicity
    - **Property 2: Temperature Monotonicity**
    - **Validates: Requirements 6.2, 6.3, 6.4**
  
  - [x] 2.4 Write property test for top-N candidate selection
    - **Property 3: Top-N Candidate Selection**
    - **Validates: Requirements 1.4**
  
  - [x] 2.5 Write property test for probabilistic selection bias
    - **Property 4: Probabilistic Selection Bias**
    - **Validates: Requirements 1.2**
  
  - [x] 2.6 Write property test for suboptimal pick range validity
    - **Property 11: Suboptimal Pick Range Validity**
    - **Validates: Requirements 4.3, 4.4**
  
  - [x] 2.7 Write property test for mistake rate frequency
    - **Property 10: Mistake Rate Frequency**
    - **Validates: Requirements 4.2**

- [x] 3. Implement strategy management
  - [x] 3.1 Create StrategyManager class
    - Implement __init__ with config and random_state parameters
    - Implement assign_strategies_to_teams() method
    - Implement get_strategy_for_team() method
    - Implement apply_strategy_to_scoring_config() method
    - _Requirements: 2.2, 2.3, 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 3.2 Write property test for strategy assignment completeness
    - **Property 8: Strategy Assignment Completeness**
    - **Validates: Requirements 2.2**
  
  - [x] 3.3 Write property test for strategy application consistency
    - **Property 9: Strategy Application Consistency**
    - **Validates: Requirements 2.3**

- [ ] 4. Implement random seed management
  - [ ] 4.1 Create random seed management utilities
    - Create get_random_state() function that accepts optional seed
    - Create seed logging functionality
    - Store random state in global or service-level variable
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 4.2 Write property test for seed reproducibility
    - **Property 6: Seed Reproducibility**
    - **Validates: Requirements 3.2**
  
  - [ ] 4.3 Write property test for non-determinism with different seeds
    - **Property 5: Non-Determinism with Different Seeds**
    - **Validates: Requirements 1.3, 3.3**

- [ ] 5. Create default configuration and file management
  - [ ] 5.1 Create default variability configuration
    - Create default_variability_config.json with reasonable baseline settings
    - Include all 5 predefined strategy profiles
    - Set variability_enabled to false by default
    - _Requirements: 8.5, 10.1_
  
  - [ ] 5.2 Implement configuration loading with fallback
    - Create load_variability_config() function
    - Handle missing file by creating default config
    - Handle invalid JSON by logging error and using default
    - Handle permission errors gracefully
    - _Requirements: 8.2, 8.4_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Integrate with auto-draft endpoint
  - [ ] 7.1 Modify auto-draft endpoint to support variability
    - Add variability_enabled check at start of make_auto_draft_pick()
    - Create _make_deterministic_pick() function with existing logic
    - Create _make_probabilistic_pick() function with new logic
    - Route to appropriate function based on variability_enabled flag
    - _Requirements: 10.2, 10.3, 10.4, 10.5_
  
  - [ ] 7.2 Implement _make_probabilistic_pick() function
    - Load variability config
    - Initialize random state
    - Get strategy manager and assign strategies
    - Get strategy for current team
    - Apply strategy to scoring config
    - Get recommendations from recommendation engine
    - Use ProbabilisticSelector to choose player
    - Draft the selected player
    - Log the pick with strategy and reasoning
    - Return response with strategy information
    - _Requirements: 1.1, 1.2, 1.3, 2.2, 2.3, 4.5, 9.1_
  
  - [ ] 7.3 Write property test for backward compatibility
    - **Property 15: Backward Compatibility**
    - **Validates: Requirements 10.2, 10.5**

- [ ] 8. Implement logging and metrics
  - [ ] 8.1 Add logging for variability events
    - Log strategy assignments at draft start
    - Log temperature and probabilities for each pick
    - Log when suboptimal picks are made
    - Log random seed used for simulation
    - _Requirements: 3.4, 4.5, 9.1, 9.5_
  
  - [ ] 8.2 Implement metrics tracking
    - Track suboptimal picks per team per simulation
    - Calculate diversity metrics across multiple simulations
    - Report percentage of picks that differ across simulations
    - _Requirements: 9.2, 9.3, 9.4_
  
  - [ ] 8.3 Write unit tests for metrics calculation
    - Test suboptimal pick counting
    - Test diversity percentage calculation
    - _Requirements: 9.2, 9.4_

- [ ] 9. Create configuration management utilities
  - [ ] 9.1 Create CLI or API endpoints for configuration management
    - Add endpoint to get current variability config
    - Add endpoint to update variability config
    - Add endpoint to enable/disable variability
    - Add endpoint to set random seed
    - _Requirements: 8.1, 8.2, 10.1_
  
  - [ ] 9.2 Write integration tests for configuration endpoints
    - Test loading and saving configurations
    - Test enabling/disabling variability
    - Test setting random seed
    - _Requirements: 8.1, 8.2_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Documentation and examples
  - [ ] 11.1 Create usage documentation
    - Document how to enable variability
    - Document how to configure strategies
    - Document how to set random seed for reproducibility
    - Provide examples of different configurations
    - _Requirements: All_
  
  - [ ] 11.2 Create example configuration files
    - Create high_variability.json example
    - Create low_variability.json example
    - Create testing.json example with fixed seed
    - _Requirements: 8.5_

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation maintains backward compatibility by default (variability_enabled=false)
- All probabilistic behavior is controlled through the VariabilityConfig
- Random seed management enables reproducible testing and debugging
