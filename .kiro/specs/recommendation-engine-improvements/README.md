# Recommendation Engine Improvements

## Quick Start

**Problem:** The recommendation engine is complex and hard to understand. You can't easily see why players are recommended or adjust the AI's decision-making.

**Solution:** Make the engine transparent and tunable with clear documentation, score breakdowns, and adjustable weights.

## What You'll Find Here

1. **`SCORING_GUIDE.md`** - **START HERE!** Plain English explanation of how the AI makes decisions
2. **`requirements.md`** - Detailed requirements for improvements
3. **`design.md`** - (To be created) Technical design for implementation
4. **`tasks.md`** - (To be created) Implementation checklist

## Current State: How It Works

Your recommendation engine calculates a score for each player by combining 10 factors:

### The Formula (Simplified)
```
Total Score = 
  Standings Improvement (×30)
  + Roster Balance (50-260 points)
  + ML Model (×3)
  + Future Availability (-150 to +120)
  + Team Needs (various)
  + Position Scarcity (15-150)
  + Category Targeting (varies)
  + Relative Advantage (×50)
  + Risk Assessment (penalty)
```

### Key Insights

**1. Standings Improvement is King**
- Calculates actual standings points gained
- Most mathematically correct measure
- Weight: 30x multiplier

**2. Roster Balance Prevents Disasters**
- IP accumulation: Ensures you meet 1000 IP minimum
- Hitter lineup: Ensures you draft enough position players
- Prevents drafting 10 pitchers in a row

**3. Future Availability is Critical**
- Don't waste picks on players available later
- Uses opponent modeling to predict survival
- Can swing scores by ±150 points

**4. ML Model Provides Intelligence**
- Trained on 44+ features
- Analyzes all contextual factors
- Weight reduced from 10x to 3x to let strategy dominate

## Problems Identified

### 1. **No Transparency**
Users see: "Bobby Witt Jr - Score: 980"  
Users want: "Bobby Witt Jr - Score: 980 (Standings: +90, Roster: +260, Availability: +120, ...)"

### 2. **Magic Numbers Everywhere**
```python
score += 260.0  # Why 260?
ml_score = ml_value * 3  # Why 3?
penalty = -150  # Why -150?
```

### 3. **Hard to Tune**
Want to make AI more aggressive on pitchers? Need to:
- Find all pitcher-related scoring code
- Understand complex interactions
- Change multiple magic numbers
- Hope you didn't break something

### 4. **No Validation**
Can't easily test if changes improve recommendations

## Proposed Improvements

### Phase 1: Transparency (User Story 1 & 3)
- Show score breakdown by factor
- Display weights used
- Improve reasoning text
- Document all factors

### Phase 2: Tunability (User Story 2)
- Centralize weights in config file
- Create UI for weight adjustment
- Support weight profiles (aggressive, balanced, safe)
- Hot-reload changes

### Phase 3: Validation (User Story 4)
- Run against historical drafts
- Compare weight configurations
- Export recommendation history
- Measure accuracy metrics

## Quick Examples

### Example 1: Why is Bobby Witt Jr Recommended?
**Current Output:**
```
Bobby Witt Jr - Score: 980
Reasoning: "Standings: +3.0 pts | Building lineup (2/11 hitters) | ~1% survival - STEAL (will be gone!)"
```

**Improved Output:**
```
Bobby Witt Jr - Score: 980

Score Breakdown:
  Standings Improvement: +90 (3.0 points × 30)
  Roster Balance: +260 (need hitters)
  ML Model: +165 (value: 55 × 3)
  Future Availability: +120 (1% survival - take now!)
  Team Needs: +80 (need SS)
  Position Scarcity: +150 (elite SS, few left)
  Category Targeting: +85 (helps R, SB)
  Relative Advantage: +30 (blocks opponents)
  Risk: +0 (low risk)

Why: Elite shortstop who fills critical need and will be gone if you don't take him now. 
Improves standings by 3 points and helps build your lineup.
```

### Example 2: Adjusting Weights
**Current:** Edit code, restart app  
**Improved:** 
```json
{
  "weights": {
    "standings_multiplier": 30,
    "ip_accumulation_base": 200,
    "hitter_lineup_bonus": 260,
    "ml_multiplier": 3,
    "availability_max_bonus": 120,
    "availability_max_penalty": -150
  }
}
```
Change in UI, see results immediately.

## Next Steps

1. **Read `SCORING_GUIDE.md`** to understand current system
2. **Review `requirements.md`** for detailed user stories
3. **Decide on implementation approach**:
   - Quick win: Add score breakdown to existing system
   - Full solution: Refactor to centralized config + UI
4. **Create design.md** with technical approach
5. **Create tasks.md** with implementation checklist

## Questions?

- **How do I make the AI draft more pitchers?** Increase `ip_accumulation_base` and `pitcher_need_bonus`
- **How do I make the AI more aggressive?** Reduce `availability_max_penalty` (less penalty for taking players early)
- **How do I trust the ML model more?** Increase `ml_multiplier` from 3 to 5-10
- **How do I see what's happening?** Implement Phase 1 (transparency)

## Files in This Spec

```
.kiro/specs/recommendation-engine-improvements/
├── README.md (this file)
├── SCORING_GUIDE.md (how the AI works - read this first!)
├── requirements.md (detailed requirements)
├── design.md (to be created)
└── tasks.md (to be created)
```
