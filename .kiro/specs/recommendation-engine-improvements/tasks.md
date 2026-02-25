# Recommendation Engine Improvements - Implementation Tasks

## Overview
Implementation plan for making the recommendation engine transparent, tunable, and testable.

**Current Status**: ScoringConfig class is complete. Now building the rest of the infrastructure.

## Task Breakdown

### Phase 1: Config Infrastructure (No Breaking Changes)

#### 1. Create Core Config Classes
- [x] 1.1 Create `src/services/scoring_config.py`
  - [x] 1.1.1 Implement `ScoringConfig` dataclass with all weights
  - [x] 1.1.2 Add `to_dict()` and `from_dict()` methods
  - [x] 1.1.3 Add `load_from_file()` and `save_to_file()` methods
  - [x] 1.1.4 Add `validate()` method with error checking
  - [x] 1.1.5 Write unit tests for ScoringConfig

- [ ] 1.2 Create `src/services/scoring_breakdown.py`
  - [ ] 1.2.1 Implement `FactorScore` dataclass with name, score, reasoning, weight_used, raw_value
  - [ ] 1.2.2 Implement `ScoringBreakdown` dataclass with player info, total_score, factors list
  - [ ] 1.2.3 Add `get_top_factors(n)` method to return top N factors by absolute score
  - [ ] 1.2.4 Add `format_summary()` method for human-readable output
  - [ ] 1.2.5 Add `to_dict()` methods for JSON serialization
  - [ ] 1.2.6 Write unit tests for FactorScore and ScoringBreakdown

- [ ] 1.3 Create `src/services/config_manager.py`
  - [ ] 1.3.1 Implement `ConfigManager` class with config_dir initialization
  - [ ] 1.3.2 Add `_load_default_profiles()` with 5 built-in profiles (default, aggressive, conservative, pitcher_heavy, hitter_heavy)
  - [ ] 1.3.3 Add `load_profile(profile_name)` method with file loading fallback
  - [ ] 1.3.4 Add `save_profile(config, profile_name)` method
  - [ ] 1.3.5 Add `list_profiles()` method returning list of dicts with name, description, version
  - [ ] 1.3.6 Add `get_current_config()` method
  - [ ] 1.3.7 Add `reset_to_default()` method
  - [ ] 1.3.8 Write unit tests for ConfigManager

- [ ] 1.4 Create default config files
  - [ ] 1.4.1 Create `config/scoring/` directory structure
  - [ ] 1.4.2 Generate and save `default.json` from ScoringConfig defaults
  - [ ] 1.4.3 Generate and save `aggressive.json` profile (higher ML weight, lower risk penalties)
  - [ ] 1.4.4 Generate and save `conservative.json` profile (higher position needs, higher risk penalties)
  - [ ] 1.4.5 Generate and save `pitcher_heavy.json` profile (higher IP bonuses, pitcher scarcity)
  - [ ] 1.4.6 Generate and save `hitter_heavy.json` profile (higher hitter bonuses, lower pitcher scarcity)

#### 2. Integrate Config into RecommendationEngine
- [ ] 2.1 Update `RecommendationEngine.__init__()`
  - [ ] 2.1.1 Import ConfigManager and ScoringConfig
  - [ ] 2.1.2 Add `self.config_manager = ConfigManager()` initialization
  - [ ] 2.1.3 Add `self.config = self.config_manager.get_current_config()` property
  - [ ] 2.1.4 Ensure backward compatibility (no breaking changes to existing code)

- [ ] 2.2 Add config management methods to RecommendationEngine
  - [ ] 2.2.1 Add `set_config_profile(profile_name)` method that loads profile and clears cache
  - [ ] 2.2.2 Add `get_config()` method that returns current config
  - [ ] 2.2.3 Add `update_config(**kwargs)` method that updates specific weights and clears cache
  - [ ] 2.2.4 Ensure cache is cleared when config changes

- [ ] 2.3 Write integration tests
  - [ ] 2.3.1 Test config loading on initialization
  - [ ] 2.3.2 Test profile switching with `set_config_profile()`
  - [ ] 2.3.3 Test config updates with `update_config()`
  - [ ] 2.3.4 Test cache invalidation when config changes

#### 3. Add Config API Endpoints
- [x] 3.1 Add config endpoints to `src/api/app.py`
  - [x] 3.1.1 Add `GET /api/recommendations/config` - Returns current config as JSON
  - [x] 3.1.2 Add `GET /api/recommendations/config/profiles` - Returns list of available profiles
  - [x] 3.1.3 Add `POST /api/recommendations/config/profile` - Sets active profile by name
  - [x] 3.1.4 Add `PATCH /api/recommendations/config` - Updates specific config values
  - [x] 3.1.5 Add `POST /api/recommendations/config/reset` - Resets to default profile

- [x] 3.2 Add error handling to config endpoints
  - [x] 3.2.1 Handle invalid profile names (404 with error message)
  - [x] 3.2.2 Handle invalid config values (400 with validation errors)
  - [x] 3.2.3 Return validation errors from `config.validate()`

- [x] 3.3 Write API tests
  - [x] 3.3.1 Test GET config endpoint returns current config
  - [x] 3.3.2 Test GET profiles endpoint returns all profiles
  - [x] 3.3.3 Test POST profile endpoint switches profiles
  - [x] 3.3.4 Test PATCH config endpoint updates values
  - [x] 3.3.5 Test error cases (invalid profile, invalid values)

### Phase 2: Refactor Scoring Methods to Use Config

#### 4. Refactor `_calculate_roster_balance_score()`
- [ ] 4.1 Replace hardcoded IP accumulation values
  - [ ] 4.1.1 Replace `200.0` with `self.config.ip_accumulation_base_0_20`
  - [ ] 4.1.2 Replace `150.0` with `self.config.ip_accumulation_base_20_50`
  - [ ] 4.1.3 Replace `100.0` with `self.config.ip_accumulation_base_50_80`
  - [ ] 4.1.4 Replace `50.0` with `self.config.ip_accumulation_base_80_100`
  - [ ] 4.1.5 Replace `0.3` with `self.config.ip_contribution_per_ip`
  
- [ ] 4.2 Replace hardcoded hitter lineup bonuses
  - [ ] 4.2.1 Replace `260.0` with `self.config.hitter_lineup_bonus_0_2`
  - [ ] 4.2.2 Replace `150.0` with `self.config.hitter_lineup_bonus_3_5`
  - [ ] 4.2.3 Replace `75.0` with `self.config.hitter_lineup_bonus_6_8`
  
- [ ] 4.3 Update return signature to `Tuple[float, str]` (score, reasoning)
- [ ] 4.4 Write unit tests for roster balance scoring with different configs

#### 5. Refactor `_analyze_future_availability_enhanced()`
- [ ] 5.1 Replace hardcoded availability bonuses
  - [ ] 5.1.1 Replace `120.0` with `self.config.availability_bonus_0_10`
  - [ ] 5.1.2 Replace `80.0` with `self.config.availability_bonus_10_30`
  - [ ] 5.1.3 Replace `30.0` with `self.config.availability_bonus_30_50`
  
- [ ] 5.2 Replace hardcoded availability penalties
  - [ ] 5.2.1 Replace `-30.0` with `self.config.availability_penalty_50_70`
  - [ ] 5.2.2 Replace `-80.0` with `self.config.availability_penalty_70_85`
  - [ ] 5.2.3 Replace `-150.0` with `self.config.availability_penalty_85_100`
  
- [ ] 5.3 Write unit tests for availability scoring

#### 6. Refactor Team Needs Scoring Methods
- [ ] 6.1 Find and update `_analyze_team_needs()` or related methods
  - [ ] 6.1.1 Replace hardcoded `80.0` with `self.config.position_need_bonus`
  - [ ] 6.1.2 Replace hardcoded `-200.0` with `self.config.redundant_position_penalty`
  - [ ] 6.1.3 Replace hardcoded `40.0` with `self.config.behind_pace_bonus`
  - [ ] 6.1.4 Replace hardcoded `60.0` with `self.config.no_pitchers_bonus`
  - [ ] 6.1.5 Replace hardcoded `-100.0` with `self.config.enough_pitchers_penalty`
  
- [ ] 6.2 Write unit tests for team needs scoring

#### 7. Refactor Position Scarcity Scoring
- [ ] 7.1 Find and update position scarcity calculations
  - [ ] 7.1.1 Replace elite position values with `self.config.elite_position_scarce` and `elite_position_moderate`
  - [ ] 7.1.2 Replace mid-tier with `self.config.mid_tier_position`
  - [ ] 7.1.3 Replace pitcher scarcity with `self.config.pitcher_scarcity_high/moderate/low/deep`
  
- [ ] 7.2 Write unit tests for position scarcity scoring

#### 8. Refactor Category Targeting Scoring
- [ ] 8.1 Find and update category weight calculations
  - [ ] 8.1.1 Replace HR weight with `self.config.category_weight_hr`
  - [ ] 8.1.2 Replace R weight with `self.config.category_weight_r`
  - [ ] 8.1.3 Replace RBI weight with `self.config.category_weight_rbi`
  - [ ] 8.1.4 Replace SB weight with `self.config.category_weight_sb`
  - [ ] 8.1.5 Replace OBP weight with `self.config.category_weight_obp`
  - [ ] 8.1.6 Replace K weight with `self.config.category_weight_k`
  - [ ] 8.1.7 Replace ERA weight with `self.config.category_weight_era`
  - [ ] 8.1.8 Replace WHIP weight with `self.config.category_weight_whip`
  - [ ] 8.1.9 Replace Wins weight with `self.config.category_weight_wins`
  - [ ] 8.1.10 Replace QS weight with `self.config.category_weight_qs`
  - [ ] 8.1.11 Replace Saves weight with `self.config.category_weight_saves`
  - [ ] 8.1.12 Replace Holds weight with `self.config.category_weight_holds`
  
- [ ] 8.2 Write unit tests for category targeting

#### 9. Refactor Relative Advantage Scoring
- [ ] 9.1 Find and update relative advantage calculations
  - [ ] 9.1.1 Replace multiplier with `self.config.relative_advantage_multiplier`
  - [ ] 9.1.2 Replace opponent strategy bonus with `self.config.opponent_strategy_bonus`
  - [ ] 9.1.3 Replace blocking bonus with `self.config.blocking_bonus_per_opponent`
  
- [ ] 9.2 Write unit tests for relative advantage scoring

#### 10. Refactor Risk Assessment Scoring
- [ ] 10.1 Find and update risk penalty calculations
  - [ ] 10.1.1 Replace injury risk penalty with `self.config.injury_risk_penalty`
  - [ ] 10.1.2 Replace age decline penalty with `self.config.age_decline_penalty`
  - [ ] 10.1.3 Replace sample size penalty with `self.config.sample_size_penalty`
  
- [ ] 10.2 Write unit tests for risk assessment

#### 11. Refactor ML Model Integration
- [ ] 11.1 Find ML model score calculation in `_calculate_player_value()`
  - [ ] 11.1.1 Replace hardcoded `3` or `3.0` multiplier with `self.config.ml_multiplier`
  
- [ ] 11.2 Write unit tests for ML scoring

#### 12. Refactor Standings Improvement Scoring
- [ ] 12.1 Find standings improvement calculation in `_calculate_player_value()`
  - [ ] 12.1.1 Replace hardcoded `30` or `30.0` multiplier with `self.config.standings_multiplier`
  
- [ ] 12.2 Write unit tests for standings scoring

#### 13. Refactor Fallback Scoring
- [ ] 13.1 Find fallback scoring logic (when ML unavailable)
  - [ ] 13.1.1 Replace ADP weight with `self.config.fallback_adp_weight`
  - [ ] 13.1.2 Replace team needs weight with `self.config.fallback_team_needs_weight`
  - [ ] 13.1.3 Replace position scarcity weight with `self.config.fallback_position_scarcity_weight`
  - [ ] 13.1.4 Replace category targeting weight with `self.config.fallback_category_targeting_weight`
  - [ ] 13.1.5 Replace relative advantage weight with `self.config.fallback_relative_advantage_weight`
  - [ ] 13.1.6 Replace risk weight with `self.config.fallback_risk_weight`
  
- [ ] 13.2 Write unit tests for fallback scoring

#### 14. Refactor Auto-Draft Scoring
- [ ] 14.1 Find auto-draft scoring logic
  - [ ] 14.1.1 Replace ADP weight with `self.config.autodraft_adp_weight`
  - [ ] 14.1.2 Replace team needs weight with `self.config.autodraft_team_needs_weight`
  - [ ] 14.1.3 Replace position scarcity weight with `self.config.autodraft_position_scarcity_weight`
  
- [ ] 14.2 Write unit tests for auto-draft scoring

#### 15. Add Breakdown Generation to `_calculate_player_value()`
- [ ] 15.1 Update method signature
  - [ ] 15.1.1 Add `return_breakdown: bool = False` parameter
  - [ ] 15.1.2 Update return type to `Union[Tuple[float, str], Tuple[float, str, ScoringBreakdown]]`
  
- [ ] 15.2 Track factor scores during calculation
  - [ ] 15.2.1 Create `factors: List[FactorScore] = []` at start of method
  - [ ] 15.2.2 After each scoring calculation, append `FactorScore` to list
  - [ ] 15.2.3 Include factor name, score contribution, reasoning, weight used, raw value
  
- [ ] 15.3 Generate breakdown when requested
  - [ ] 15.3.1 Import ScoringBreakdown and FactorScore
  - [ ] 15.3.2 Create `ScoringBreakdown` object with player info, total score, factors, profile name
  - [ ] 15.3.3 Return `(score, reasoning, breakdown)` when `return_breakdown=True`
  - [ ] 15.3.4 Return `(score, reasoning)` when `return_breakdown=False` (backward compatible)
  
- [ ] 15.4 Write integration tests for breakdown generation

#### 16. Add Breakdown to API
- [ ] 16.1 Update `get_recommendations()` method
  - [ ] 16.1.1 Add `include_breakdown: bool = False` parameter
  - [ ] 16.1.2 Pass `return_breakdown=include_breakdown` to `_calculate_player_value()`
  - [ ] 16.1.3 Handle both 2-tuple and 3-tuple returns
  - [ ] 16.1.4 Include breakdown in recommendation dict when available
  
- [ ] 16.2 Update `/api/recommendations` endpoint
  - [ ] 16.2.1 Add `?breakdown=true` query parameter support
  - [ ] 16.2.2 Pass `include_breakdown` to `get_recommendations()`
  - [ ] 16.2.3 Serialize breakdown to JSON in response
  
- [ ] 16.3 Write API tests for breakdown endpoint

### Phase 3: UI Enhancements (Optional - User-Facing)

#### 17. Add Breakdown Display to Frontend (Optional)
- [ ]* 17.1 Update recommendation card UI in `frontend/src/ui-renderer.ts`
  - [ ]* 17.1.1 Add "View Breakdown" button/link to each recommendation
  - [ ]* 17.1.2 Add expandable breakdown section with collapse/expand functionality
  - [ ]* 17.1.3 Display factor scores in table format (factor name, score, reasoning)
  - [ ]* 17.1.4 Highlight top 3 factors with visual emphasis
  - [ ]* 17.1.5 Add tooltips for factor explanations

- [ ]* 17.2 Update API client in `frontend/src/api.ts`
  - [ ]* 17.2.1 Add `getRecommendationsWithBreakdown()` method with `?breakdown=true` param
  - [ ]* 17.2.2 Parse breakdown data from response
  - [ ]* 17.2.3 Handle missing breakdown gracefully (fallback to regular display)

- [ ]* 17.3 Add CSS styling in `frontend/static/css/style.css`
  - [ ]* 17.3.1 Style breakdown table with proper spacing and borders
  - [ ]* 17.3.2 Add expand/collapse animations
  - [ ]* 17.3.3 Add responsive design for mobile devices

#### 18. Create Config UI - Simple Mode (Optional)
- [ ]* 18.1 Add config panel to UI
  - [ ]* 18.1.1 Create config settings section in main UI
  - [ ]* 18.1.2 Add profile dropdown selector with all available profiles
  - [ ]* 18.1.3 Display current profile name and description
  - [ ]* 18.1.4 Add "Advanced Settings" button to open advanced mode

- [ ]* 18.2 Implement profile switching
  - [ ]* 18.2.1 Call `POST /api/recommendations/config/profile` on selection
  - [ ]* 18.2.2 Show loading indicator during switch
  - [ ]* 18.2.3 Refresh recommendations after successful switch
  - [ ]* 18.2.4 Show success/error messages with toast notifications

- [ ]* 18.3 Add profile descriptions
  - [ ]* 18.3.1 Show tooltip with full profile description on hover
  - [ ]* 18.3.2 Add "Learn More" link to documentation

#### 19. Create Config UI - Advanced Mode (Optional)
- [ ]* 19.1 Create advanced config modal/page
  - [ ]* 19.1.1 Group weights by category (Primary, Roster Balance, Availability, etc.)
  - [ ]* 19.1.2 Add number inputs for each weight with labels
  - [ ]* 19.1.3 Add descriptions/tooltips for each weight explaining what it does
  - [ ]* 19.1.4 Add validation (min/max ranges, visual feedback)

- [ ]* 19.2 Add config actions
  - [ ]* 19.2.1 Add "Save as Profile" button to create custom profile
  - [ ]* 19.2.2 Add "Reset to Default" button to restore defaults
  - [ ]* 19.2.3 Add "Export Config" button to download JSON file
  - [ ]* 19.2.4 Add "Import Config" button to upload JSON file

- [ ]* 19.3 Implement config updates
  - [ ]* 19.3.1 Call `PATCH /api/recommendations/config` on save
  - [ ]* 19.3.2 Show validation errors from server
  - [ ]* 19.3.3 Refresh recommendations after successful update
  - [ ]* 19.3.4 Show success confirmation message

- [ ]* 19.4 Add real-time preview (Optional)
  - [ ]* 19.4.1 Show estimated impact of weight changes
  - [ ]* 19.4.2 Highlight changed values in different color
  - [ ]* 19.4.3 Add "Undo" button to revert changes

#### 20. Add Profile Management UI (Optional)
- [ ]* 20.1 Create profile management section
  - [ ]* 20.1.1 List all available profiles with cards
  - [ ]* 20.1.2 Show profile details (name, description, version)
  - [ ]* 20.1.3 Add "Edit" button for custom profiles
  - [ ]* 20.1.4 Add "Delete" button for custom profiles
  - [ ]* 20.1.5 Add "Duplicate" button to create custom from existing

- [ ]* 20.2 Implement profile CRUD operations
  - [ ]* 20.2.1 Create new profile from current config
  - [ ]* 20.2.2 Edit existing custom profile
  - [ ]* 20.2.3 Delete custom profile with confirmation
  - [ ]* 20.2.4 Prevent editing/deleting built-in profiles

### Phase 4: Validation & Documentation

#### 21. Historical Draft Validation (Optional)
- [ ]* 21.1 Create validation script `scripts/validate_config.py`
  - [ ]* 21.1.1 Load historical draft data from `data/league_analysis/draft_history/`
  - [ ]* 21.1.2 Run recommendations at each pick in historical drafts
  - [ ]* 21.1.3 Compare recommendations to actual picks made
  - [ ]* 21.1.4 Calculate accuracy metrics (top-5 accuracy, ADP correlation)

- [ ]* 21.2 Test different profiles
  - [ ]* 21.2.1 Run validation for each built-in profile
  - [ ]* 21.2.2 Compare profile performance across metrics
  - [ ]* 21.2.3 Identify best profile for different draft scenarios

- [ ]* 21.3 Generate validation report
  - [ ]* 21.3.1 Report accuracy by profile
  - [ ]* 21.3.2 Report value captured (ADP vs actual pick)
  - [ ]* 21.3.3 Report roster balance achieved
  - [ ]* 21.3.4 Provide recommendations for tuning

#### 22. Weight Sensitivity Analysis (Optional)
- [ ]* 22.1 Create sensitivity testing script
  - [ ]* 22.1.1 Test extreme weight values (0, 2x, 5x default)
  - [ ]* 22.1.2 Identify unstable configurations that break recommendations
  - [ ]* 22.1.3 Document recommended ranges for each weight

- [ ]* 22.2 Generate sensitivity report
  - [ ]* 22.2.1 Show impact of each weight on recommendation order
  - [ ]* 22.2.2 Identify interaction effects between weights
  - [ ]* 22.2.3 Provide recommended min/max values

#### 23. Documentation
- [x] 23.1 Update `README.md`
  - [x] 23.1.1 Add section on config management and profiles
  - [x] 23.1.2 Add examples of using config API
  - [x] 23.1.3 Link to new documentation files

- [ ]* 23.2 Create `CONFIG_GUIDE.md` (Optional)
  - [ ]* 23.2.1 Explain how to adjust weights
  - [ ]* 23.2.2 Describe each profile and use cases
  - [ ]* 23.2.3 Provide weight recommendations and ranges
  - [ ]* 23.2.4 Add troubleshooting section for common issues
  - [ ]* 23.2.5 Include examples and tutorials

- [ ]* 23.3 Create `API_REFERENCE.md` (Optional)
  - [ ]* 23.3.1 Document all config endpoints with examples
  - [ ]* 23.3.2 Provide request/response examples
  - [ ]* 23.3.3 Document error codes and handling
  - [ ]* 23.3.4 Note authentication requirements (none for local)

#### 24. Tune Default Profiles (Optional)
- [ ]* 24.1 Analyze validation results
  - [ ]* 24.1.1 Identify best-performing weights from validation
  - [ ]* 24.1.2 Adjust default profile based on historical data
  - [ ]* 24.1.3 Tune other profiles for specific strategies

- [ ]* 24.2 Update profile configs
  - [ ]* 24.2.1 Update `default.json` with tuned weights
  - [ ]* 24.2.2 Update other profile JSON files
  - [ ]* 24.2.3 Document changes and rationale in comments

- [ ]* 24.3 Re-run validation
  - [ ]* 24.3.1 Verify improvements in metrics
  - [ ]* 24.3.2 Compare before/after performance
  - [ ]* 24.3.3 Document final results

### Phase 5: Testing & Quality Assurance

#### 25. Comprehensive Testing
- [ ] 25.1 Run all unit tests
  - [ ] 25.1.1 Run `pytest tests/` and verify all tests pass
  - [ ] 25.1.2 Check coverage with `pytest --cov=src` (target 80%+ for new code)
  - [ ] 25.1.3 Fix any failing tests
  - [ ] 25.1.4 Add missing tests for uncovered code

- [ ] 25.2 Run integration tests
  - [ ] 25.2.1 Test end-to-end recommendation flow with config
  - [ ] 25.2.2 Test all API endpoints manually or with integration tests
  - [ ] 25.2.3 Test profile switching during active draft

- [ ] 25.3 Run regression tests
  - [ ] 25.3.1 Verify existing functionality unchanged (backward compatibility)
  - [ ] 25.3.2 Test with existing saved drafts
  - [ ] 25.3.3 Verify recommendations still work without config changes

- [ ] 25.4 Performance testing
  - [ ] 25.4.1 Measure recommendation response time with breakdown
  - [ ] 25.4.2 Measure breakdown generation overhead
  - [ ] 25.4.3 Verify < 2 second target met for recommendations

#### 26. Manual Testing
- [ ] 26.1 Test core functionality
  - [ ] 26.1.1 Start a draft and verify recommendations work
  - [ ] 26.1.2 Switch profiles and verify recommendations change
  - [ ] 26.1.3 Update config values and verify immediate effect
  - [ ] 26.1.4 Request breakdown and verify display

- [ ] 26.2 Test edge cases
  - [ ] 26.2.1 Test with extreme weight values (very high/low)
  - [ ] 26.2.2 Test with invalid config (should show validation errors)
  - [ ] 26.2.3 Test with missing config files (should use defaults)
  - [ ] 26.2.4 Test error handling and recovery

## Success Criteria

### Completion Criteria
- [x] All Phase 1-2 tasks complete (config infrastructure and refactoring)
- [x] All unit tests passing with 80%+ coverage for new code
- [x] API endpoints working and tested
- [x] Documentation updated (README.md minimum)
- [x] Backward compatibility maintained (existing drafts work)

### Quality Metrics
- Code coverage: 80%+ for new code
- Performance: < 2 seconds for recommendations
- Breakdown overhead: < 10%
- No regressions in existing functionality

## Notes

- **Phase 1-2 are required** for core functionality
- **Phase 3-4 are optional** (UI enhancements, validation, advanced docs)
- **Phase 5 is required** for quality assurance
- Maintain backward compatibility throughout
- Test thoroughly at each phase
- Optional tasks marked with `*` after checkbox
