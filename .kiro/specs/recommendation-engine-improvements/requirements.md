# Recommendation Engine Improvements - Requirements

## Overview
Improve the AI recommendation engine to make it more transparent, tunable, and effective. The current system is complex with multiple scoring factors, but lacks visibility into how decisions are made and easy ways to adjust the weighting.

## Problem Statement
The recommendation engine currently:
1. **Lacks transparency**: Hard to understand why a player is recommended
2. **Has hidden weights**: Scoring factors are scattered throughout the code with magic numbers
3. **Is difficult to tune**: Changing weights requires code changes and understanding complex interactions
4. **No validation**: Can't easily test if changes improve recommendations

## User Stories

### 1. Understanding Recommendations
**As a** fantasy baseball drafter  
**I want to** see a clear breakdown of why each player is recommended  
**So that** I can trust the AI's decisions and learn draft strategy

**Acceptance Criteria:**
- [ ] 1.1 Each recommendation shows a score breakdown by factor (standings improvement, team needs, scarcity, etc.)
- [ ] 1.2 Weights for each factor are clearly displayed
- [ ] 1.3 Reasoning text explains the top 2-3 factors driving the recommendation
- [ ] 1.4 Can see "what-if" scenarios (e.g., "If you draft this player, your standings points would increase by X")

### 2. Tuning Weights
**As a** power user  
**I want to** adjust the importance of different factors  
**So that** I can customize recommendations to my draft strategy

**Acceptance Criteria:**
- [ ] 2.1 All scoring weights are centralized in a configuration file
- [ ] 2.2 Can adjust weights through a UI or config file without code changes
- [ ] 2.3 Changes take effect immediately (no restart required)
- [ ] 2.4 Can save/load different weight profiles (e.g., "aggressive", "balanced", "safe")
- [ ] 2.5 Can reset to default weights

### 3. Scoring Factor Documentation
**As a** developer or advanced user  
**I want to** understand what each scoring factor does  
**So that** I can make informed decisions about tuning

**Acceptance Criteria:**
- [ ] 3.1 Documentation explains each scoring factor in plain English
- [ ] 3.2 Shows the formula/calculation for each factor
- [ ] 3.3 Provides examples of when each factor matters most
- [ ] 3.4 Explains interactions between factors

### 4. Validation & Testing
**As a** developer  
**I want to** validate that weight changes improve recommendations  
**So that** I can measure the impact of tuning

**Acceptance Criteria:**
- [ ] 4.1 Can run recommendations against historical drafts
- [ ] 4.2 Can compare different weight configurations
- [ ] 4.3 Shows metrics: accuracy, value captured, roster balance
- [ ] 4.4 Can export recommendation history for analysis

## Current Scoring Factors (Discovered from Code)

### Primary Factors
1. **Standings Improvement** (30x multiplier)
   - Calculates actual standings points gained by drafting this player
   - Most mathematically correct measure of value
   
2. **IP Accumulation Bonus** (for pitchers below 1000 IP)
   - Base bonus: 50-200 points depending on progress
   - IP contribution: 0.3 per projected IP
   - Critical for meeting league minimum

3. **Hitter Lineup Bonus** (when building lineup)
   - 0-2 hitters: +260 points
   - 3-5 hitters: +150 points
   - 6-8 hitters: +75 points

### Secondary Factors
4. **ML Model Prediction** (3x multiplier, when available)
   - Trained on 44+ features including all contextual factors
   - Reduced from 10x to give strategy factors more weight

5. **Future Availability** (-150 to +120 points)
   - Survival probability based on opponent needs
   - Penalizes players likely available later
   - Rewards players who will be gone

6. **Team Needs** (various bonuses/penalties)
   - Position requirements: +80 per unfilled position
   - Redundant picks: -200 penalty
   - Behind pace on pitchers: +40-60 bonus

7. **Position Scarcity** (15-150 points)
   - Elite positions (C, SS): 100-150 points
   - Pitchers: 15-50 points (conservative)
   - Deep positions: 20-80 points

8. **Category Targeting** (varies by category priority)
   - Weights categories based on standings position
   - Higher priority for categories where you're behind

9. **Relative Advantage** (50 points per standings point)
   - Analyzes how player helps vs opponents
   - Considers opponent strategies

10. **Risk Assessment** (penalty for high-risk players)
    - Injury risk, age decline, sample size concerns

### Fallback Scoring (when ML unavailable)
- Custom ADP: 50% weight
- Contextual factors: 50% weight
  - Team needs: 30%
  - Position scarcity: 25%
  - Category targeting: 20%
  - Relative advantage: 15%
  - Risk: 10%

## Key Issues Identified

### 1. Magic Numbers Everywhere
```python
score += base_bonus + ip_contribution_value  # What's the reasoning?
score += 260.0  # Why 260?
ml_score = ml_value * 3  # Why 3?
```

### 2. Complex Interactions
- IP bonus can override standings improvement
- Availability penalties can negate team needs
- Hard to predict how changes affect final scores

### 3. No Visibility
- Users see final score and brief reasoning
- Can't see individual factor contributions
- Can't understand why Player A > Player B

### 4. Difficult to Tune
- Weights scattered across multiple methods
- Need to understand code to change behavior
- No way to A/B test different configurations

## Success Metrics

### Quantitative
- Recommendation accuracy: % of top-5 recommendations that would be good picks
- Value captured: Average ADP vs pick number for recommended players
- Roster balance: % of drafts that meet position requirements without issues
- User satisfaction: Survey rating of recommendation quality

### Qualitative
- Users can explain why a player was recommended
- Users feel confident adjusting weights for their strategy
- Developers can easily add new scoring factors
- System is maintainable and testable

## Out of Scope
- Changing the core recommendation algorithm (keep existing factors)
- Adding new data sources
- Redesigning the UI (focus on backend transparency)
- Real-time opponent modeling (keep simplified approach)

## Technical Constraints
- Must maintain backward compatibility with existing drafts
- Performance: Recommendations must return in < 2 seconds
- No external dependencies (keep local-only architecture)
- Must work with existing ML models

## Future Enhancements (Not in This Spec)
- Machine learning model retraining with new weights
- Multi-objective optimization (Pareto frontier)
- Opponent-specific strategy modeling
- Real-time weight adjustment based on draft flow
