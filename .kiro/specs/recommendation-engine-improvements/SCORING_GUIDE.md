# Recommendation Engine Scoring Guide

## How the AI Makes Decisions

This guide explains how your draft assistant evaluates players and makes recommendations.

## The Big Picture

The recommendation engine calculates a **total score** for each available player by combining multiple factors. Higher scores = better recommendations.

**Final Score = Standings + Roster Balance + ML Model + Strategy Factors + Availability**

---

## Scoring Factors Explained

### 1. Standings Improvement (PRIMARY METRIC)
**Weight: 30x multiplier**  
**What it does:** Calculates how many standings points you'd gain by drafting this player

This is the most mathematically correct way to value players. The system:
1. Calculates your current projected standings points
2. Calculates your projected standings points WITH this player
3. The difference = standings improvement

**Example:**
- Current standings: 65 points (out of 130 possible)
- With Bobby Witt Jr: 68 points
- Improvement: +3 points
- Score contribution: 3 × 30 = **+90 points**

**Why it matters:** This directly measures how much this player helps you win your league.

---

### 2. Roster Balance Bonuses

#### IP Accumulation (Pitchers)
**Weight: 50-200 base + 0.3 per IP**  
**What it does:** Ensures you draft enough pitchers to meet the 1000 IP minimum

Your league requires 1,000 innings pitched to qualify in pitching categories. Below that, you get LAST PLACE (1 point) in all 5 pitching categories - a massive handicap.

**Bonus Scale:**
- 0-200 IP (0-20%): +200 base bonus
- 200-500 IP (20-50%): +150 base bonus
- 500-800 IP (50-80%): +100 base bonus
- 800-1000 IP (80-100%): +50 base bonus
- Above 1000 IP: Standings improvement takes over

**Example:**
- You have 300 IP (30% of minimum)
- Pitcher projects 180 IP
- Score: 150 (base) + (180 × 0.3) = **+204 points**

#### Hitter Lineup Bonus
**Weight: 75-260 points**  
**What it does:** Ensures you draft enough hitters to fill your lineup

You need 11 hitters (C, 1B, 2B, 3B, SS, MI, CI, 4 OF, U). The system encourages balance:

**Bonus Scale:**
- 0-2 hitters: +260 points
- 3-5 hitters: +150 points
- 6-8 hitters: +75 points
- 9+ hitters: No bonus

**Why it matters:** Prevents you from drafting 10 pitchers in a row and having no lineup.

---

### 3. ML Model Prediction (When Available)
**Weight: 3x multiplier**  
**What it does:** Uses machine learning trained on historical drafts to predict player value

The ML model analyzes 44+ features including:
- Player stats (HR, K, ERA, etc.)
- Team needs (positions, categories)
- Position scarcity
- Draft context (round, pick number)
- Opponent strategies
- Risk factors

**Output:** 0-100 value score  
**Score contribution:** ML value × 3

**Example:**
- ML predicts value of 45 for Juan Soto
- Score contribution: 45 × 3 = **+135 points**

**Note:** Reduced from 10x multiplier to let strategy factors (availability, roster needs) have more influence.

---

### 4. Future Availability (CRITICAL)
**Weight: -150 to +120 points**  
**What it does:** Predicts if this player will still be available at your next pick

This prevents wasting early picks on players you could get later. The system:
1. Calculates survival probability based on:
   - Player's ADP vs picks until your next turn
   - How many opponents need this position
   - How many opponents need IP (for pitchers)
2. Adjusts score based on urgency

**Survival Probability → Score Adjustment:**
- < 10% survival: +120 (STEAL - will be gone!)
- 10-30%: +80 (Value pick)
- 30-50%: +30 (Take now or risk losing)
- 50-70%: -30 (Borderline)
- 70-85%: -80 (Available later)
- > 85%: -150 (Wait - definitely available)

**Example:**
- Pick 15, your next pick is ~40
- Cristopher Sanchez (ADP 33): 85% survival
- Score adjustment: **-150 points** (wait for him)
- Bobby Witt Jr (ADP 3): 1% survival
- Score adjustment: **+120 points** (take now!)

**Why it matters:** This is opportunity cost - don't waste picks on players you can get later.

---

### 5. Team Needs
**Weight: Various bonuses/penalties**  
**What it does:** Identifies gaps in your roster and prioritizes filling them

**Position Requirements:**
- Unfilled position: +80 per position needed
- Redundant pick (3+ at same position): -200 penalty
- Can fill flexible slot (MI, CI, U): +20-40 bonus

**Pitcher Pacing:**
- Behind pace (should have more pitchers by this round): +40-60 bonus
- No pitchers by round 4+: +60 bonus
- Have enough pitchers: -100 penalty

**IP Requirements:**
- Below 1000 IP: Bonus for IP contribution (see Roster Balance)
- Would exceed 1400 IP: -200 penalty

**Example:**
- You have 0 catchers (need 1)
- Drafting a catcher: **+80 points**
- You have 3 outfielders (need 4)
- Drafting 5th outfielder: **-200 points** (redundant)

---

### 6. Position Scarcity
**Weight: 15-150 points**  
**What it does:** Values positions that are running out of quality players

**Elite Positions (C, SS, 2B, 3B):**
- Elite player, few elite left: +150 points
- Elite player, some elite left: +100 points
- Mid-tier player: +50 points

**Pitchers (Conservative):**
- 70+ pitchers drafted: +50 points
- 50+ pitchers drafted: +35 points
- Truly scarce: +25 points
- Deep pool: +15 points

**Deep Positions (OF):**
- Very scarce (< 0.5 ratio): +80 points
- Moderate scarcity: +50 points
- Deep pool: +20 points

**Why it matters:** Elite catchers and shortstops are rare - grab them early.

---

### 7. Category Targeting
**Weight: Varies by category priority (0.3-1.0)**  
**What it does:** Prioritizes categories where you're behind opponents

The system:
1. Calculates your current category totals
2. Compares to opponent medians
3. Assigns priority (0-1) to each category
4. Weights player contributions by priority

**Example:**
- You have 15 HR, opponents average 25 HR
- HR priority: 0.8 (high)
- Player projects 35 HR
- Score: 35 × 2.5 (HR weight) × 0.8 (priority) = **+70 points**

**Category Weights:**
- HR: 2.5 per home run
- R: 0.6 per run
- RBI: 0.6 per RBI
- SB: 3.5 per stolen base
- OBP: 500 × (OBP - 0.300)
- K: 0.1 per strikeout
- ERA: 50 × (5.0 - ERA) / 3.0 (lower is better)
- WHIP: 50 × (1.50 - WHIP) / 0.60 (lower is better)
- Wins: 2.0 per win
- QS: 2.0 per quality start
- Saves: 3.0 per save
- Holds: 1.5 × (holds × 0.5)

---

### 8. Relative Advantage
**Weight: 50 points per standings point**  
**What it does:** Analyzes how this player helps you vs opponents

Considers:
- Opponent strategies (heavy hitters vs heavy pitchers)
- Blocking value (preventing opponents from getting this player)
- Position runs (many teams drafting same position)

**Example:**
- Opponents going heavy on pitchers
- You draft elite hitter
- Score: **+30 points** (counter-strategy bonus)

---

### 9. Risk Assessment
**Weight: Penalty for high-risk players**  
**What it does:** Reduces score for injury-prone or unreliable players

Factors:
- Injury history
- Age decline
- Small sample size
- Contract year uncertainty

**Example:**
- Player with injury history
- Score: **-20 to -50 points** (risk penalty)

---

## Fallback Scoring (When ML Model Unavailable)

If the ML model isn't loaded, the system uses rule-based scoring:

**Weights:**
- Custom ADP: 50%
- Team needs: 30% of contextual score
- Position scarcity: 25% of contextual score
- Category targeting: 20% of contextual score
- Relative advantage: 15% of contextual score
- Risk: 10% of contextual score

Total: **50% ADP + 50% Contextual**

---

## Auto-Draft Mode (Simplified Scoring)

For speed, auto-draft uses simplified scoring:

**Weights:**
- ADP value: 60%
- Team needs: 30%
- Position scarcity: 10%

Skips: Category targeting, relative advantage, risk assessment, lookahead simulation

---

## How Scores Combine

**Example: Bobby Witt Jr at Pick 15**

1. Standings improvement: +3 points × 30 = **+90**
2. Hitter lineup bonus (have 2 hitters): **+260**
3. ML model: 55 × 3 = **+165**
4. Future availability: 1% survival = **+120**
5. Team needs: Need SS = **+80**
6. Position scarcity: Elite SS, few left = **+150**
7. Category targeting: Helps with R, SB = **+85**
8. Relative advantage: Blocks opponents = **+30**
9. Risk: Low risk = **+0**

**Total Score: 980 points**

---

## Common Questions

### Q: Why is the AI recommending pitchers so early?
**A:** You're likely below the 1000 IP minimum. The IP accumulation bonus (+200) ensures you don't get stuck with 1 point in all pitching categories.

### Q: Why isn't the AI recommending my favorite player?
**A:** Check the availability score. If they have high survival probability (>85%), the AI thinks you can get them later (-150 penalty).

### Q: How do I make the AI more aggressive/conservative?
**A:** Currently requires code changes. See the "Tuning Weights" user story in requirements.md for planned improvements.

### Q: Why do scores seem so high/low?
**A:** Scores are relative. A score of 500 vs 300 means the first player is better, but the absolute numbers don't have inherent meaning.

---

## Tips for Understanding Recommendations

1. **Look at the reasoning text** - Shows top 2-3 factors
2. **Check survival probability** - High survival = wait
3. **Monitor IP accumulation** - Below 1000 IP = prioritize pitchers
4. **Watch roster balance** - Need 11 hitters, 9 pitchers
5. **Trust standings improvement** - Most mathematically correct metric

---

## Next Steps

See `requirements.md` for planned improvements:
- Score breakdowns by factor
- Adjustable weights through UI
- Validation against historical drafts
- Weight profiles (aggressive, balanced, safe)
