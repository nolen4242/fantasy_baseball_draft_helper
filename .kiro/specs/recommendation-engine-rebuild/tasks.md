# Implementation Plan: Recommendation Engine Rebuild

## Overview

Rebuild the recommendation engine by creating 4 new service modules (PlayerLoader, ZScoreCalculator, ReplacementLevelAnalyzer, SavantAdjuster), refactoring the existing RecommendationEngine into a slim compositor, removing ML scaffolding, and wiring everything through app.py. Each task builds incrementally so the system stays functional at each checkpoint.

## Tasks

- [x] 1. Create PlayerLoader service
  - [x] 1.1 Create `src/services/player_loader.py` with the `PlayerLoader` class
    - Implement `load()` method that reads `data/master_players.json` and returns `(List[Player], Dict[str, dict])`
    - Implement `_create_player()` to map a JSON entry to a `Player` dataclass, populating projection fields from the `blended` key
    - Implement `_map_position()` with `POSITION_MAP` to convert RF/LF/CF → OF, DH → U, and pass through other positions
    - Implement `_resolve_adp()` to prefer `nfbc_adp`, fall back to `cbs_adp`, else `None`
    - Implement `_extract_savant()` to return the most recent season's Savant data dict from `savant_history`
    - Handle missing `blended` key by creating Player with `None` projection fields
    - Handle missing `savant_history` gracefully (no entry stored)
    - Skip entries missing `name` or `player_id` with a logged warning
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 1.2 Write property tests for PlayerLoader
    - **Property 1: Player loading round-trip** — for any valid entry with a `blended` key, the resulting Player's projection fields match the blended values
    - **Validates: Requirement 1.1**
    - **Property 2: ADP resolution priority** — resolved ADP equals `nfbc_adp` when present, else `cbs_adp`, else `None`
    - **Validates: Requirements 1.2, 1.3**
    - **Property 3: Savant data keyed by player ID** — for entries with savant history, `savant_data` contains the player_id key with most recent season stats
    - **Validates: Requirements 1.5, 5.8**
    - **Property 4: Position mapping preserves valid draft positions** — mapped positions are always valid draft positions, and OF variants map to OF
    - **Validates: Requirement 1.6**

  - [x] 1.3 Write unit tests for PlayerLoader
    - Load actual `data/master_players.json` and verify known players (e.g., Aaron Judge) have correct field values
    - Test entries with missing blended data produce Player with None projections
    - Test ADP fallback logic with entries having only cbs_adp
    - Test position mapping for RF, LF, CF, DH
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

- [x] 2. Create ZScoreCalculator service
  - [x] 2.1 Create `src/services/zscore_calculator.py` with the `ZScoreCalculator` class
    - Define `BATTING_CATEGORIES`, `PITCHING_CATEGORIES`, `INVERTED_CATEGORIES` class constants
    - Implement `calculate()` that returns `Dict[str, Dict[str, float]]` keyed by player_id with per-category z-scores and composite
    - Implement `_compute_stats()` to compute mean and stddev for each category across the relevant player pool
    - Implement `_player_category_value()` to extract raw values, computing SHOLDS as `projected_saves + (projected_holds × 0.5)` and WQS as `projected_wins + projected_quality_starts`
    - Implement `_zscore()` with inversion for ERA/WHIP (lower is better → higher z-score) and return 0.0 when stddev is zero
    - Separate hitters and pitchers for z-score computation (hitters get batting categories, pitchers get pitching categories)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 2.2 Write property tests for ZScoreCalculator
    - **Property 5: Z-score formula correctness** — each z-score equals `(value - mean) / std` and composite equals sum of category z-scores
    - **Validates: Requirements 3.1, 3.3, 3.4**
    - **Property 6: Inverted z-scores for rate categories** — pitcher with lower ERA has higher z-score than pitcher with higher ERA (same for WHIP)
    - **Validates: Requirement 3.2**
    - **Property 7: Derived category formulas** — SHOLDS = saves + holds×0.5, WQS = wins + quality_starts
    - **Validates: Requirements 3.6, 3.7**

  - [x] 2.3 Write unit tests for ZScoreCalculator
    - Hand-computed z-score example with 3–4 players
    - Verify zero-stddev edge case returns 0.0
    - Verify SHOLDS and WQS formulas with known values
    - Verify ERA/WHIP inversion
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7_

- [x] 3. Create ReplacementLevelAnalyzer service
  - [x] 3.1 Create `src/services/replacement_level.py` with the `ReplacementLevelAnalyzer` class
    - Define `POSITION_SLOTS` dict (C:13, 1B:13, ..., OF:52, P:117) and `FLEX_ELIGIBLE` dict
    - Implement `analyze()` that returns `Dict[str, float]` keyed by player_id → VAR
    - Implement `_replacement_level()` to find the composite z-score of the player at the roster-slot boundary for a position
    - Implement `_eligible_for_position()` to check if a player can fill a given position slot, including flex eligibility (MI accepts 2B/SS, CI accepts 1B/3B, U accepts any hitter)
    - Multi-position players use the position yielding the highest VAR
    - Handle edge cases: fewer players than slots, no players at a position
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.2 Write property tests for ReplacementLevelAnalyzer
    - **Property 8: VAR computation** — VAR equals player composite z-score minus replacement-level composite at the best position
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - **Property 9: Replacement level recalculation** — replacement level changes when above-replacement players are removed from the pool
    - **Validates: Requirement 4.4**
    - **Property 10: Flex position combined pool** — flex replacement level is drawn from the combined eligible pool
    - **Validates: Requirement 4.5**

  - [x] 3.3 Write unit tests for ReplacementLevelAnalyzer
    - Small pool (5 players, 2 positions) with hand-computed replacement levels and VAR
    - Test multi-position player uses best position
    - Test flex position eligibility
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [x] 4. Checkpoint — Verify core valuation services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create SavantAdjuster service
  - [x] 5.1 Create `src/services/savant_adjuster.py` with the `SavantAdjuster` class
    - Define league-average baselines as class constants (AVG_BARREL_RATE, AVG_EXIT_VELO, AVG_SPRINT_SPEED, AVG_XWOBA)
    - Implement `adjust()` returning `(float, Optional[str])` — adjustment score and signal string (e.g., "Buy-low: xwOBA .418 vs actual .373")
    - Implement `_hitter_adjustment()` using xwOBA gap for buy-low/sell-high, barrel rate and exit velocity for power reliability, sprint speed for SB reliability
    - Implement `_pitcher_adjustment()` using xwOBA-against and expected ERA indicators
    - Return `(0.0, None)` when savant data is None or missing key metrics
    - Use most recent available season from savant_history (prefer 2024/2025)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x] 5.2 Write property tests for SavantAdjuster
    - **Property 11: xwOBA adjustment direction** — sign of adjustment matches sign of (xwOBA - actual) when gap exceeds threshold
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - **Property 12: Above-average Savant metrics produce non-negative adjustments** — above-avg barrel rate + exit velo → non-negative power adjustment; above-avg sprint speed → non-negative speed adjustment
    - **Validates: Requirements 5.4, 5.5**
    - **Property 13: Pitcher Savant adjustment direction** — lower xwOBA-against than actual implies positive adjustment
    - **Validates: Requirement 5.6**

  - [x] 5.3 Write unit tests for SavantAdjuster
    - Known buy-low candidate (high xwOBA, low actual OBP)
    - Known sell-high candidate (low xwOBA, high actual OBP)
    - Player with no savant data returns (0.0, None)
    - Pitcher with favorable xwOBA-against
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 5.7_

- [x] 6. Refactor RecommendationEngine as compositor
  - [x] 6.1 Refactor `src/services/recommendation_engine.py` to use new services
    - Replace the constructor to accept `players`, `savant_data`, and optional `weights` dict
    - Instantiate `ZScoreCalculator`, `ReplacementLevelAnalyzer`, `SavantAdjuster` in `__init__`
    - Define `DEFAULT_WEIGHTS` dict for the 9 scoring components
    - Rewrite `get_recommendations()` to: compute z-scores and VAR for the undrafted pool, then score each candidate via `_score_player()`
    - Implement `_score_player()` that computes the weighted sum of 9 components and builds the reasoning string
    - Return top 10–30 recommendations sorted by descending composite score
    - Remove `_analyze_projected_value()` method (replaced by z-scores + VAR)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 6.2 Refactor position scarcity scoring in the engine
    - Clean up `_analyze_position_scarcity()` → `_score_position_scarcity()` using above-average player count vs teams needing the position
    - Treat catcher as inherently scarce
    - Handle flex positions using combined eligible pool
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 6.3 Refactor team needs scoring in the engine
    - Clean up `_analyze_team_needs()` → `_score_team_needs()` checking roster against required slots (11 hitters, 9 pitchers)
    - Apply positive bonus for unfilled positions, negative for maxed positions
    - Account for flex eligibility (MI, CI, U)
    - Maintain baseline positive score for pitchers while team has < 9
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 6.4 Refactor relative advantage scoring in the engine
    - Clean up `_analyze_relative_advantage()` → `_score_relative_advantage()` using StandingsCalculator
    - Larger bonus for bottom-third categories (9th–13th), smaller for top-third (1st–4th)
    - Evaluate all 10 scoring categories
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 6.5 Refactor ADP value scoring in the engine
    - Clean up `_analyze_adp_value()` → `_score_adp_value()` with tiered reach penalties
    - Positive score when ADP > current pick (value), negative when ADP < current pick (reach)
    - Tiered penalties: small reaches (1–3 picks) penalized less than large reaches (10+)
    - No adjustment when ADP is None
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 6.6 Implement pitcher caps and closer needs scoring
    - Implement `_score_pitcher_caps()` with reduced scores at 7+ pitchers, large negative at 9+
    - Closer bonus logic: 0 closers after pick 80, 1 closer after pick 130, 2 closers after pick 180
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 6.7 Implement category balance scoring
    - Implement `_score_category_balance()` using StandingsCalculator for projected totals
    - Activate only when team has 5+ players
    - Bonus when losing to 8+ opponents in a category and player improves it
    - Correctly handle rate categories (ERA, WHIP decrease = improvement)
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 7. Remove ML scaffolding
  - [x] 7.1 Remove all ML-related code from the engine and app
    - Remove `MLTrainer` import and `ml_trainer` instance from `app.py`
    - Remove `train_ml_models()` endpoint from `app.py`
    - Remove `_ml_models_loaded` flag, `use_ml` parameter, and ML prediction branches from the engine
    - Remove `master_player_dict` initialization from `app.py` (replaced by PlayerLoader)
    - Remove `DataLoader` import and `data_loader` initialization from `app.py` (replaced by PlayerLoader)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 8. Checkpoint — Verify engine refactor
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Wire PlayerLoader into app.py and integrate API
  - [x] 9.1 Update `app.py` initialization to use PlayerLoader
    - Replace old CSV/DataLoader/MasterPlayerDict initialization with `PlayerLoader().load()`
    - Pass `all_players` and `savant_data` to the new `RecommendationEngine` constructor
    - Update `get_recommendations()` to remove `use_ml` parameter and call the refactored engine
    - Ensure `/api/recommendations` response shape stays identical: `{'recommendations': [{'player': {...}, 'score': float, 'reasoning': str}]}`
    - Remove old `load_players()`, `load_steamer_files()`, `load_cbs_data()` endpoints if they are no longer needed, or keep them as no-ops returning success for frontend compatibility
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 9.2 Write property tests for composite scoring and recommendations
    - **Property 24: Composite score is weighted sum** — final score equals weighted sum of 9 component scores
    - **Validates: Requirements 12.1, 12.2**
    - **Property 25: Recommendations sorted by descending score** — each score >= next score in the list
    - **Validates: Requirement 12.4**
    - **Property 26: Recommendation count bounds** — returns between 10 and 30 recommendations when 10+ players available
    - **Validates: Requirement 12.5**
    - **Property 27: Savant signals appear in reasoning** — buy-low/sell-high signals present in reasoning string
    - **Validates: Requirements 12.3, 13.4**

  - [x] 9.3 Write integration tests for the full engine
    - Small draft scenario (5 teams, 10 players) verifying composite score matches manual calculation
    - Verify `/api/recommendations` returns expected JSON shape with `player`, `score`, and `reasoning` fields
    - _Requirements: 12.1, 13.1_

- [x] 10. Write remaining property tests for scoring factors
  - [x] 10.1 Write property tests for position scarcity
    - **Property 14: Position scarcity monotonicity** — as above-average players decrease relative to teams needing the position, scarcity score increases
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.5**

  - [x] 10.2 Write property tests for team needs
    - **Property 15: Unfilled position needs bonus** — unfilled position + eligible player → positive needs score
    - **Validates: Requirement 7.2**
    - **Property 16: Filled position negative adjustment** — maxed position → negative needs score for additional player
    - **Validates: Requirement 7.3**
    - **Property 17: Flex position eligibility in needs** — 2B/SS fills MI, 1B/3B fills CI, any hitter fills U
    - **Validates: Requirement 7.4**
    - **Property 18: Pitcher baseline needs** — team with < 9 pitchers → non-negative needs score for pitchers
    - **Validates: Requirement 7.5**

  - [x] 10.3 Write property tests for relative advantage and ADP
    - **Property 19: Relative advantage scales with ranking** — bottom-third bonus > top-third bonus for same category improvement
    - **Validates: Requirements 8.2, 8.3**
    - **Property 20: ADP value monotonicity** — positive when ADP > pick, negative when ADP < pick, magnitude increases with gap
    - **Validates: Requirements 9.1, 9.2, 9.4**

  - [x] 10.4 Write property tests for pitcher caps and category balance
    - **Property 21: Pitcher cap penalty increases with count** — penalty more negative at 9+ pitchers than 7–8
    - **Validates: Requirements 10.1, 10.2**
    - **Property 22: Closer bonus decreases with closer count** — largest at 0 closers, smaller at 1, smallest at 2
    - **Validates: Requirements 10.3, 10.4, 10.5**
    - **Property 23: Category balance activates at 5+ players** — zero balance score below 5 players, positive bonus when losing to 8+ opponents
    - **Validates: Requirements 11.1, 11.2**

- [x] 11. Create test infrastructure
  - [x] 11.1 Create `tests/conftest.py` with shared Hypothesis strategies and fixtures
    - `player_strategy()` — generates random Player instances with valid projection ranges
    - `player_pool_strategy()` — generates lists of 50–200 players with realistic position distributions
    - `savant_strategy()` — generates random Savant stat dicts with realistic ranges
    - `draft_state_strategy()` — generates DraftState with 0–200 picks made
    - `weights_strategy()` — generates random weight dicts with values 0.0–2.0
    - Shared pytest fixtures for common test setups

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1–27)
- Unit tests validate specific examples and edge cases
- The engine refactor (task 6) preserves existing scoring logic for position scarcity, team needs, relative advantage, ADP value, pitcher caps, and category balance — it cleans and reorganizes rather than rewriting from scratch
- All Python code uses `python3` for execution
