# Recent Changes - January 8, 2026

## Summary
Major improvements to the recommendation engine focusing on **mathematically correct draft strategy** and **opponent-aware availability analysis**.

---

## 1. IP Accumulation Fix

### Problem
The recommendation engine was recommending 4+ outfielders in a row without taking pitchers, even though the league requires 1000 IP minimum to qualify in pitching categories.

### Root Cause
The `standings_improvement` calculation returned 0 for pitchers because you don't gain standings points until you cross the 1000 IP threshold. Below 1000 IP, you're stuck at 1 point (last place) in all 5 pitching categories regardless of how many pitchers you have.

### Solution
Implemented IP accumulation bonus that scales with progress toward 1000 IP minimum:
- **< 20% progress**: +200 base bonus + IP contribution value
- **20-50% progress**: +150 base bonus
- **50-80% progress**: +100 base bonus  
- **80-100% progress**: +50 base bonus
- **Above 1000 IP**: Standings improvement takes over

---

## 2. Future Availability / Opportunity Cost

### Problem
The model recommended Cristopher Sanchez (ADP ~33) over elite hitters like Tatis and Gunnar (ADP ~5-15), even though Sanchez would likely still be available at the next pick while Tatis/Gunnar would be gone.

### Solution
Implemented `_analyze_future_availability_enhanced()` that calculates **player survival probability** based on:

1. **ADP vs picks until next turn** - baseline survival estimate
2. **Opponent roster needs** - how many opponents need this position
3. **IP demand** - how many opponents need pitching (for pitchers)

### Survival Probability → Score Adjustment
| Survival | Adjustment | Meaning |
|----------|------------|---------|
| < 10% | +120 bonus | STEAL - will be gone! |
| 10-30% | +80 bonus | Value pick |
| 30-50% | +30 bonus | Take now or risk losing |
| 50-70% | -30 penalty | Borderline |
| 70-85% | -80 penalty | Available later |
| > 85% | -150 penalty | Wait - definitely available |

---

## 3. Opponent Modeling

### New Function: `_calculate_player_survival_probability()`

Analyzes opponent rosters to predict demand:
- Counts how many opponents need each position (C, SS, 1B, 2B, 3B, OF)
- Counts how many opponents need pitching/IP
- Adjusts survival probability based on demand
- Elite positions (C, SS) have higher demand factors

### Example
At pick 2 with 13 teams:
- Your next pick is ~27
- Bobby Witt Jr (SS, ADP 3.26): ~1% survival (12 teams need SS)
- Cristopher Sanchez (P, ADP 33): ~4% survival (lower demand, higher ADP)

---

## 4. Roster Balance Bonuses

### Hitter Lineup Bonus (when building lineup)
- **0-2 hitters**: +260 points
- **3-5 hitters**: +150 points
- **6-8 hitters**: +75 points

### Pitcher IP Bonus (when below 1000 IP)
- Base bonus: +200 points (scales with progress)
- IP contribution: +0.3 per projected IP

---

## 5. ML Model Scaling

Reduced ML model influence from `ml_value * 10` to `ml_value * 3` to let draft strategy factors (survival, roster needs) have more weight in recommendations.

---

## Files Modified
- `src/services/recommendation_engine.py` - Main changes
- `src/services/standings_calculator.py` - Caching improvements
- `src/models/player.py` - Added dataclass validation

---

## Testing Notes
The system now correctly:
1. Prioritizes pitchers when at 0 IP until reaching ~1000 IP
2. Switches to hitters once IP minimum is met
3. Shows survival probability in recommendations
4. Factors in opponent needs when calculating availability
5. Penalizes high-ADP players who will be available later
6. Rewards low-ADP players who will be gone if not taken

---

## Known Tuning Considerations
- Elite hitters (Witt ADP 3, Soto ADP 4) currently rank slightly higher than elite pitchers (Skubal ADP 7) due to lower ADPs
- The survival bonus provides differentiation but may need further tuning based on actual draft results
- Opponent modeling is simplified (assumes random opponent picks) - could be enhanced with opponent-specific strategy prediction
