# Data Architecture for AI Training

## Data Directory Structure

```
data/
├── sources/                          # Raw data from external sources
│   ├── baseball_reference/
│   │   ├── standard_stats/          # Counting stats (R, RBI, HR, etc.)
│   │   │   ├── batters_2024.csv
│   │   │   ├── pitchers_2024.csv
│   │   │   └── historical/          # Previous years
│   │   ├── advanced_stats/          # wRC+, ERA+, OPS+, etc.
│   │   │   ├── batters_2024.csv
│   │   │   └── pitchers_2024.csv
│   │   └── projections/             # BBRef conservative projections
│   │       ├── batters_2025.csv
│   │       └── pitchers_2025.csv
│   ├── baseball_savant/
│   │   ├── statcast/                # Statcast data
│   │   │   ├── batters_2024.csv
│   │   │   └── pitchers_2024.csv
│   │   ├── park_factors/            # Park factor data
│   │   │   └── park_factors_2024.csv
│   │   └── historical/              # Historical Statcast data
│   ├── fangraphs/
│   │   ├── projections/             # Multiple projection systems
│   │   │   ├── steamer_batters_2025.csv
│   │   │   ├── steamer_pitchers_2025.csv
│   │   │   ├── zips_batters_2025.csv
│   │   │   ├── zips_pitchers_2025.csv
│   │   │   ├── thebat_batters_2025.csv
│   │   │   └── atc_batters_2025.csv
│   │   └── historical/             # Historical Fangraphs data
│   ├── bb_forecaster/
│   │   └── predictions_2025.csv
│   ├── rotowire/
│   │   ├── news/                    # Player news, qualitative data
│   │   │   └── player_news_2025.json
│   │   └── injuries/
│   │       ├── injury_history.csv
│   │       └── current_injuries.json
│   ├── nfbc/
│   │   ├── adp/                     # Professional ADP data
│   │   │   └── nfbc_adp_2025.csv
│   │   └── draft_history/          # Historical draft results
│   │       └── nfbc_drafts_2024.json
│   └── cbs/
│       ├── position_eligibility/    # Position eligibility data
│       │   └── positions_2025.csv
│       ├── historical_drafts/      # Historical draft data
│       │   └── cbs_drafts_2024.json
│       └── league_thresholds/      # Stats needed to win league
│           └── winning_thresholds_2024.json
│
├── processed/                       # Processed and merged data
│   ├── master_players.json         # Unified player database
│   ├── player_features.json        # Engineered features for ML
│   └── training_data/              # Prepared training datasets
│       └── training_features.csv
│
├── models/                          # Trained ML models
│   ├── value_model.pkl
│   ├── risk_model.pkl
│   └── feature_scaler.pkl
│
└── batters/                         # Legacy (keep for compatibility)
    └── ...
```

## Data Source Specifications

### Baseball Reference
**Standard Stats (batters):**
- R, RBI, HR, SB, H, 2B, 3B, BB, SO, AVG, OBP, SLG, OPS
- MVPs, All-Star appearances, Gold Gloves

**Standard Stats (pitchers):**
- W, L, SV, IP, H, R, ER, BB, SO, ERA, WHIP
- Cy Young awards, All-Star appearances

**Advanced Stats:**
- wRC+, OPS+, ERA+, FIP, xFIP, WAR
- Park-adjusted metrics

**Projections:**
- Conservative BBRef projection system

### Baseball Savant
**Statcast Data:**
- Exit velocity, launch angle, barrel rate
- Hard hit %, xBA, xSLG, xwOBA
- Spin rate, pitch movement, velocity
- Sprint speed, defensive metrics

**Park Factors:**
- Offensive park factors
- Pitching park factors
- Home run factors

### Fangraphs
**Projection Systems:**
- Steamer
- ZiPS
- THE BAT
- ATC (Average of multiple systems)

### BB Forecaster
- Prediction market data
- Consensus predictions

### Rotowire
**News Data (JSON):**
- Player news, updates
- Contract signings
- Prospect call-ups
- Personal factors (family, motivation)

**Injury Data:**
- Historical injury records
- Current injury status
- Injury risk scores
- Recovery timelines

### NFBC
**ADP Data:**
- Professional draft ADP
- High-stakes league data
- Positional ADP

**Draft History:**
- Historical draft results
- When players were taken
- Position scarcity patterns

### CBS
**Position Eligibility:**
- Multi-position eligibility
- Games played at each position

**Historical Drafts:**
- When players were drafted
- Position scarcity impact
- Value per pick

**League Thresholds:**
- Stats needed to win each category
- Category targets (HR, R, RBI, SB, ERA, WHIP, etc.)

## Feature Engineering Strategy

### Player-Level Features
1. **Statistical Features**
   - Standard stats (R, RBI, HR, etc.)
   - Advanced stats (wRC+, ERA+, etc.)
   - Statcast metrics (exit velocity, spin rate, etc.)
   - Multiple projection systems (Steamer, ZiPS, etc.)

2. **Risk Features**
   - Injury history score
   - Age and decline curve
   - Sample size confidence (prospects vs veterans)
   - Contract year motivation

3. **Context Features**
   - Park factors (home park)
   - Team context (lineup position, role)
   - News sentiment (positive/negative)

4. **Draft Context Features**
   - ADP (NFBC professional)
   - Historical draft position
   - Position scarcity score

### Team-Level Features
1. **Current Roster State**
   - Category totals
   - Position needs
   - Hitter/pitcher balance

2. **Opponent Analysis**
   - Opponent category totals
   - Opponent position needs
   - Competitive gaps

3. **Draft Context**
   - Current pick number
   - Round number
   - Picks remaining
   - ADP relevance (decreases after round 15)

### Comparative Advantage Features
1. **Category Gaps**
   - How much this player closes gaps vs opponents
   - Category improvement potential

2. **Position Scarcity**
   - Available players at position
   - Remaining slots needed
   - Elite players remaining

3. **Value Per Pick**
   - Historical value at this pick number
   - Position scarcity value
   - ADP deviation value

## Training Data Approach

Instead of simulated drafts, use:
1. **Historical Draft Data** (NFBC, CBS)
   - Real draft results
   - Final standings
   - What picks led to wins

2. **Feature Engineering**
   - Extract features for each historical pick
   - Calculate final team rank
   - Train on real outcomes

3. **Target Variable**
   - Final league rank (1-13)
   - Category wins
   - Total points

## Recommendation Logic Updates

1. **Early Rounds (1-15):** Heavy ADP weighting
2. **Mid Rounds (16-20):** Balance ADP, needs, scarcity
3. **Late Rounds (21+):** Focus on needs, ignore ADP

4. **Position Scarcity:** Dynamic based on remaining players
5. **Comparative Advantage:** Maximize category gains vs opponents
6. **Risk Assessment:** Factor in injury risk, age, sample size

