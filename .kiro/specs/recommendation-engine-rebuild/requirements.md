# Requirements Document

## Introduction

Rebuild the fantasy baseball draft recommendation engine for the Bob Uecker Imaginary Baseball League. The current engine (`src/services/recommendation_engine.py`) scores players across 8 factors but suffers from broken projection loading, dead ML scaffolding, and arbitrary stat multipliers. This rebuild replaces the data pipeline with `data/master_players.json`, introduces z-score based player valuation, replacement-level analysis, and Savant-informed adjustments while preserving and improving the working scoring factors (position scarcity, team needs, relative advantage, ADP value, pitcher caps, category balance).

## Glossary

- **Engine**: The `RecommendationEngine` class in `src/services/recommendation_engine.py` that scores and ranks available players during a draft
- **Player_Loader**: A new service that reads `data/master_players.json` and hydrates `Player` model instances with blended projections, ADP, and Savant data
- **Z_Score_Calculator**: A component that computes each player's value as standard deviations above or below the mean in each scoring category, relative to position-eligible peers
- **Replacement_Level_Analyzer**: A component that determines the value of the last draftable player at each position and measures each player's value above that baseline
- **Savant_Adjuster**: A component that uses Statcast metrics (xwOBA, barrel rate, exit velocity, sprint speed) from `savant_history` to identify players whose projections may understate or overstate true talent
- **Scoring_Compositor**: The top-level scoring function within the Engine that combines z-score value, replacement-level value, Savant adjustments, position scarcity, team needs, relative advantage, ADP value, pitcher caps, and category balance into a final recommendation score
- **Draft_State**: The `DraftState` model tracking all picks made, current round, current pick, and team rosters
- **Standings_Calculator**: The existing `StandingsCalculator` service that computes rotisserie category totals and rankings across all 13 teams
- **Master_Players_JSON**: The file `data/master_players.json` containing 746 players with CBS data, NFBC ADP, blended projections from 3 systems, and 5 years of Savant history
- **Blended_Projections**: The averaged projections across Steamer, ATC, and Depth Charts systems stored in the `blended` key of each player entry in Master_Players_JSON
- **SHOLDS**: Saves + (Holds × 0.5), a composite pitching category
- **WQS**: Wins + Quality Starts, a composite pitching category
- **Batting_Categories**: HR, OBP, R, RBI, SB
- **Pitching_Categories**: ERA, K, SHOLDS, WHIP, WQS
- **Position_Pool**: The set of undrafted players eligible for a given roster position (C, 1B, 2B, 3B, SS, MI, CI, OF, U, P)
- **Flex_Position**: MI (2B/SS eligible), CI (1B/3B eligible), U (any hitter), which accept multiple primary positions

## Requirements

### Requirement 1: Load Players from Master Database

**User Story:** As a user, I want the app to load all player data from `data/master_players.json` instead of the old CSV-based pipeline, so that I have accurate blended projections, ADP, and Savant data for every player.

#### Acceptance Criteria

1. WHEN the application starts a draft, THE Player_Loader SHALL read Master_Players_JSON and create a `Player` instance for each entry, populating all projection fields from the `blended` key
2. WHEN a player entry in Master_Players_JSON contains an `nfbc_adp` value, THE Player_Loader SHALL set the Player's `adp` field to that value
3. WHEN a player entry in Master_Players_JSON contains a `cbs_adp` value but no `nfbc_adp` value, THE Player_Loader SHALL fall back to `cbs_adp` for the Player's `adp` field
4. WHEN a player entry in Master_Players_JSON lacks blended projections, THE Player_Loader SHALL still create the Player instance with available fields and leave projection fields as None
5. THE Player_Loader SHALL store Savant history data in an accessible structure keyed by player ID so that the Savant_Adjuster can retrieve it during scoring
6. THE Player_Loader SHALL map position strings from Master_Players_JSON (e.g., "RF", "LF", "CF") to the position categories used by the draft system (e.g., "OF") while preserving the original position for display
7. THE Player_Loader SHALL NOT depend on `DataLoader`, `MasterPlayerDict`, or any files in the `old-data/` directory

### Requirement 2: Remove ML Scaffolding

**User Story:** As a developer, I want all ML-related code removed from the recommendation engine, so that the codebase is clean and free of dead code paths.

#### Acceptance Criteria

1. THE Engine SHALL NOT import or reference `MLTrainer` or any ML training module
2. THE Engine SHALL NOT contain any `ml_models_loaded` flag, ML prediction scoring branch, or `use_ml` parameter
3. THE Engine SHALL NOT expose any ML training API endpoint
4. WHEN the Engine calculates a player's score, THE Scoring_Compositor SHALL NOT include any ML prediction component

### Requirement 3: Z-Score Based Player Valuation

**User Story:** As a user, I want players valued using z-scores instead of arbitrary stat multipliers, so that each category contributes proportionally to a player's overall value.

#### Acceptance Criteria

1. WHEN blended projections are available for the player pool, THE Z_Score_Calculator SHALL compute the mean and standard deviation for each of the 10 scoring categories (HR, OBP, R, RBI, SB, ERA, K, SHOLDS, WHIP, WQS) across all players with projections at the relevant position type (hitters or pitchers)
2. WHEN computing z-scores for rate categories (ERA, WHIP), THE Z_Score_Calculator SHALL invert the z-score so that lower ERA/WHIP produces a higher (positive) z-score
3. WHEN a player has blended projections, THE Z_Score_Calculator SHALL compute that player's z-score in each applicable category as (player_value - mean) / standard_deviation
4. THE Z_Score_Calculator SHALL sum a player's individual category z-scores into a composite z-score value representing overall fantasy value
5. IF the standard deviation for a category is zero, THEN THE Z_Score_Calculator SHALL assign a z-score of 0.0 for that category
6. WHEN computing SHOLDS for a pitcher, THE Z_Score_Calculator SHALL calculate it as projected_saves + (projected_holds × 0.5), consistent with the league scoring rule
7. WHEN computing WQS for a pitcher, THE Z_Score_Calculator SHALL calculate it as projected_wins + projected_quality_starts, consistent with the league scoring rule

### Requirement 4: Replacement-Level Analysis

**User Story:** As a user, I want to see how much better a player is compared to the last draftable player at that position, so that I can identify positions where elite talent provides the biggest edge.

#### Acceptance Criteria

1. WHEN a draft is active, THE Replacement_Level_Analyzer SHALL determine the replacement-level player for each position by identifying the player at the boundary of draftable supply (total roster slots across 13 teams for that position among undrafted players)
2. THE Replacement_Level_Analyzer SHALL calculate each player's Value Above Replacement (VAR) as the difference between the player's composite z-score and the replacement-level player's composite z-score at the same position
3. WHEN a player is eligible for multiple positions (e.g., a 2B eligible for MI), THE Replacement_Level_Analyzer SHALL use the position where the player provides the highest VAR
4. WHEN the draft progresses and players are drafted, THE Replacement_Level_Analyzer SHALL recalculate replacement levels based on the remaining undrafted player pool
5. FOR Flex_Position slots (MI, CI, U), THE Replacement_Level_Analyzer SHALL determine replacement level from the combined pool of eligible players for that flex slot

### Requirement 5: Savant-Informed Adjustments

**User Story:** As a user, I want the engine to use Statcast data to flag players whose projections may be too conservative or too aggressive, so that I can find buy-low and sell-high candidates.

#### Acceptance Criteria

1. WHEN a hitter has Savant history data, THE Savant_Adjuster SHALL compare the player's most recent xwOBA to the player's actual wOBA (derived from OBP or batting stats) to identify over-performers and under-performers
2. WHEN a hitter's most recent xwOBA exceeds the actual performance metric by a meaningful margin, THE Savant_Adjuster SHALL apply a positive adjustment to the player's score, indicating a buy-low candidate
3. WHEN a hitter's most recent xwOBA falls below the actual performance metric by a meaningful margin, THE Savant_Adjuster SHALL apply a negative adjustment to the player's score, indicating a sell-high candidate
4. WHEN a hitter has Savant history with barrel rate and exit velocity data, THE Savant_Adjuster SHALL factor above-average barrel rate and exit velocity as positive indicators for power projection reliability
5. WHEN a hitter has sprint speed data in Savant history, THE Savant_Adjuster SHALL factor above-average sprint speed as a positive indicator for stolen base projection reliability
6. WHEN a pitcher has Savant history data, THE Savant_Adjuster SHALL use expected stats (xwOBA against, xERA if derivable) to assess whether the pitcher's ERA/WHIP projections are sustainable
7. IF a player has no Savant history data, THEN THE Savant_Adjuster SHALL apply no adjustment and use projections at face value
8. THE Savant_Adjuster SHALL use the most recent available season from the player's Savant history (preferring 2024 or 2025 data)

### Requirement 6: Position Scarcity Scoring

**User Story:** As a user, I want the engine to account for how thin each position is in the remaining player pool, so that I prioritize scarce positions before the talent runs out.

#### Acceptance Criteria

1. WHEN scoring a player, THE Engine SHALL calculate position scarcity by comparing the number of above-average players remaining at that position to the number of teams still needing that position
2. WHEN a position has fewer above-average remaining players than teams needing that position, THE Engine SHALL increase the player's scarcity score proportionally to the shortage
3. WHEN a position has abundant remaining talent, THE Engine SHALL assign a lower scarcity score for players at that position
4. THE Engine SHALL treat catcher (C) as inherently scarce due to the shallow talent pool at that position
5. WHEN computing scarcity for Flex_Position slots (MI, CI, U), THE Engine SHALL consider the combined eligible player pool rather than treating flex positions as independent pools

### Requirement 7: Team Needs Scoring

**User Story:** As a user, I want the engine to prioritize filling my roster's empty positions and avoid redundant picks, so that I end up with a complete, legal roster.

#### Acceptance Criteria

1. WHEN scoring a player for my team, THE Engine SHALL check the current roster against the required 11 hitter slots (C, 1B, 2B, 3B, SS, MI, CI, 4×OF, U) and 9 pitcher slots
2. WHEN my team has an unfilled required position and the player fills that position, THE Engine SHALL apply a positive needs bonus
3. WHEN my team already has the maximum number of players at a position, THE Engine SHALL apply a negative score adjustment for additional players at that position
4. THE Engine SHALL account for Flex_Position eligibility (MI accepts 2B/SS, CI accepts 1B/3B, U accepts any hitter) when determining whether a position need is filled
5. WHILE my team has fewer than 9 pitchers, THE Engine SHALL maintain a baseline positive score for pitchers to ensure adequate pitching staff construction

### Requirement 8: Relative Advantage Scoring

**User Story:** As a user, I want the engine to consider how my category totals compare to opponents, so that I target categories where I can gain the most rotisserie points.

#### Acceptance Criteria

1. WHEN scoring a player, THE Engine SHALL use the Standings_Calculator to compare my team's projected category totals against all 12 opponent teams
2. WHEN my team ranks in the bottom third (9th-13th) in a category, THE Engine SHALL apply a larger bonus for players who improve that category
3. WHEN my team ranks in the top third (1st-4th) in a category, THE Engine SHALL apply a smaller bonus for further improvement in that category, reflecting diminishing returns
4. THE Engine SHALL evaluate all 10 scoring categories (5 batting, 5 pitching) when computing relative advantage

### Requirement 9: ADP Value Scoring

**User Story:** As a user, I want the engine to identify players available later than their ADP suggests, so that I can find value picks and avoid reaching.

#### Acceptance Criteria

1. WHEN a player's ADP is later than the current pick number, THE Engine SHALL apply a positive value score proportional to how far the player has fallen past ADP
2. WHEN a player's ADP is earlier than the current pick number, THE Engine SHALL apply a negative score (reach penalty) proportional to how far ahead of ADP the pick would be
3. WHEN a player has no ADP data, THE Engine SHALL not apply any ADP-based adjustment
4. THE Engine SHALL use tiered reach penalties so that small reaches (1-3 picks) are penalized less than large reaches (10+ picks)

### Requirement 10: Pitcher Roster Cap and Closer Needs

**User Story:** As a user, I want the engine to enforce pitcher roster limits and ensure I draft enough closers for the SHOLDS category, so that my pitching staff is well-constructed.

#### Acceptance Criteria

1. WHILE my team has 7 or more pitchers, THE Engine SHALL reduce scores for additional pitchers to prioritize hitter slots
2. WHILE my team has 9 or more pitchers, THE Engine SHALL apply a large negative adjustment to additional pitcher scores
3. WHEN my team has zero closers (players with projected_saves >= 10) and the draft has passed pick 80, THE Engine SHALL apply a bonus for closer-eligible players
4. WHEN my team has exactly one closer and the draft has passed pick 130, THE Engine SHALL apply a smaller bonus for a second closer
5. WHEN my team has exactly two closers and the draft has passed pick 180, THE Engine SHALL apply a minor bonus for a third closer

### Requirement 11: Category Balance Scoring

**User Story:** As a user, I want the engine to boost players who shore up my weakest categories relative to opponents, so that I build a balanced roster that competes across all 10 categories.

#### Acceptance Criteria

1. WHILE my team has 5 or more players drafted, THE Engine SHALL evaluate category balance by comparing my projected totals to opponent totals in each of the 10 scoring categories
2. WHEN my team is losing to 8 or more opponents in a category and a player improves that category, THE Engine SHALL apply a category balance bonus
3. THE Engine SHALL use the Standings_Calculator to project category totals for the balance evaluation
4. WHEN evaluating rate categories (ERA, WHIP), THE Engine SHALL correctly identify improvement as a decrease in the rate value

### Requirement 12: Composite Score Assembly

**User Story:** As a user, I want all scoring factors combined into a single recommendation score with transparent reasoning, so that I can understand why each player is recommended.

#### Acceptance Criteria

1. THE Scoring_Compositor SHALL combine the following components into a final score: z-score value, replacement-level VAR, Savant adjustment, position scarcity, team needs, relative advantage, ADP value, pitcher caps, and category balance
2. THE Scoring_Compositor SHALL apply configurable weights to each scoring component so that the balance between components can be tuned
3. WHEN returning recommendations, THE Engine SHALL include a human-readable reasoning string for each player that lists the contributing factors and their individual scores
4. THE Engine SHALL return recommendations sorted by final composite score in descending order
5. WHEN the Engine generates recommendations, THE Engine SHALL return a minimum of 10 and a maximum of 30 player recommendations

### Requirement 13: API and Frontend Integration

**User Story:** As a user, I want the rebuilt engine to work seamlessly with the existing draft UI, so that I see updated recommendations without any frontend breakage.

#### Acceptance Criteria

1. THE Engine SHALL expose recommendations through the existing `/api/recommendations` endpoint with the same response shape (list of player objects with score and reasoning fields)
2. WHEN the frontend requests recommendations, THE Engine SHALL return results within 2 seconds for a typical mid-draft scenario (150 players drafted, 596 remaining)
3. THE Engine SHALL be initialized with players loaded from Master_Players_JSON instead of the old CSV pipeline, without requiring changes to the frontend code
4. WHEN a player's Savant data indicates a buy-low or sell-high signal, THE Engine SHALL include that signal in the reasoning string so the frontend can display it
