# Implementation Guide: Real-World Data Training

## Overview

This guide explains how to implement the new data-driven training system that uses real-world baseball data sources instead of simulated drafts.

## Step 1: Data Collection 

### Baseball Reference
1. **Standard Stats**: Export player statistics (R, RBI, HR, SB, W, SV, etc.) for previous season
2. **Advanced Stats**: Export wRC+, OPS+, ERA+, FIP, WAR
3. **Projections**: Export BBRef conservative projections for upcoming season

**File Format**: CSV with columns: Name, R, RBI, HR, SB, W, SV, etc.

### Baseball Savant
1. **Statcast Data**: Export Statcast metrics (exit velocity, barrel rate, xBA, xwOBA, spin rate, velocity)
2. **Park Factors**: Export park factor data (offense, pitching, HR factors)

**File Format**: CSV with Statcast columns

### Fangraphs
1. **Projections**: Download projections from multiple systems:
   - Steamer
   - ZiPS
   - THE BAT
   - ATC (Average of systems)

**File Format**: CSV with projection columns

### Rotowire
1. **News Data**: Create JSON file with player news, sentiment, contract info
2. **Injury Data**: CSV with injury history and risk scores

**JSON Format**:
```json
[
  {
    "player_name": "Aaron Judge",
    "news_text": "Signed extension",
    "sentiment": 0.8,
    "contract_year": false,
    "big_contract": true,
    "prospect_called_up": false
  }
]
```

### NFBC
1. **ADP Data**: Export professional ADP data
2. **Draft History**: Export historical draft results (JSON)

**CSV Format**: Player Name, ADP, Std Dev, Min, Max

### CBS
1. **Position Eligibility**: CSV with player positions
2. **Historical Drafts**: JSON with draft results
3. **League Thresholds**: JSON with stats needed to win

**League Thresholds JSON**:
```json
{
  "HR": 350,
  "R": 1200,
  "RBI": 1200,
  "SB": 180,
  "OBP": 0.340,
  "W": 95,
  "K": 1400,
  "ERA": 3.50,
  "WHIP": 1.20
}
```

## Step 2: Data Loading

### Using the Unified Data Merger

```python
from src.services.unified_data_merger import UnifiedDataMerger
from src.services.master_player_dict import MasterPlayerDict

# Load base players (from CBS or existing data)
master_dict = MasterPlayerDict()
base_players = master_dict.get_players_with_projections('batters') + \
               master_dict.get_players_with_projections('pitchers')

# Merge all data sources
merger = UnifiedDataMerger()
merged_players = merger.merge_all_sources(base_players, year=2025)
```

## Step 3: Feature Engineering

The `FeatureEngineer` class extracts 10 categories of features:

1. **Player Statistical Features**: Historical counting stats
2. **Projection Features**: Multiple projection systems (Steamer, ZiPS, etc.)
3. **Advanced Metrics**: wRC+, ERA+, WAR, etc.
4. **Statcast Features**: Exit velocity, barrel rate, xwOBA, etc.
5. **Risk Features**: Injury risk, age decline, sample size confidence
6. **Context Features**: Draft position, round, BB Forecaster predictions
7. **Team State Features**: Current roster totals, position needs
8. **Position Scarcity Features**: Available players, slots remaining
9. **Comparative Advantage Features**: Category improvements, opponent passing
10. **ADP Features**: Dynamic ADP weighting (less relevant after round 15)

## Step 4: Training on Historical Draft Data

### Option A: NFBC Historical Drafts

```python
from src.services.nfbc_loader import NFBCLoader
from src.services.feature_engineer import FeatureEngineer
from src.services.ml_trainer import MLTrainer

# Load historical drafts
nfbc_loader = NFBCLoader()
historical_drafts = nfbc_loader.load_draft_history(year=2024)

# Extract features for each pick
feature_engineer = FeatureEngineer()
training_data = []

for draft in historical_drafts:
    for pick in draft['picks']:
        player = find_player_by_id(pick['player_id'])
        my_team = get_team_roster_at_pick(draft, pick['team'], pick['pick_number'])
        all_rosters = get_all_rosters_at_pick(draft, pick['pick_number'])
        
        features = feature_engineer.extract_features_for_pick(
            player=player,
            my_team=my_team,
            all_players=all_available_players,
            draft_state=draft_state,
            all_team_rosters=all_rosters,
            league_thresholds=league_thresholds
        )
        
        # Target: final team rank
        final_rank = draft['final_standings'][pick['team']]
        features['target_final_rank'] = final_rank
        
        training_data.append(features)

# Train model
trainer = MLTrainer()
df = pd.DataFrame(training_data)
trainer.train_models(df)
```

### Option B: CBS Historical Drafts

Similar process using CBS historical draft data.

## Step 5: Updated Recommendation Engine

The recommendation engine now uses:

1. **ML Model Predictions**: Trained on historical data
2. **Dynamic ADP Weighting**: 
   - Rounds 1-15: Heavy ADP weight
   - Rounds 16-20: Balanced ADP/needs
   - Round 21+: Ignore ADP, focus on needs
3. **Position Scarcity**: Real-time calculation based on remaining players
4. **Comparative Advantage**: Maximize category gains vs opponents
5. **Risk Assessment**: Factor in injury risk, age, sample size

## Step 6: API Integration

### New Endpoint: Load All Data Sources

```python
@app.route('/api/data/load-all-sources', methods=['POST'])
def load_all_sources():
    """Load and merge all data sources."""
    merger = UnifiedDataMerger()
    base_players = get_base_players()  # From CBS or existing
    merged_players = merger.merge_all_sources(base_players, year=2025)
    
    # Update global player list
    global all_players
    all_players = merged_players
    
    return jsonify({
        'success': True,
        'count': len(merged_players),
        'message': 'All data sources loaded and merged'
    })
```

### Updated Recommendation Endpoint

The recommendation endpoint automatically uses the new feature engineering:

```python
@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    # ... existing code ...
    
    # Feature engineer now uses all data sources
    recommendations = recommendation_engine.get_recommendations_for_team(
        available_players=available,
        team_players=team_players,
        draft_state=draft_state,
        team_name=team_name,
        use_ml=True  # Uses new ML model trained on real data
    )
    
    return jsonify(recommendations)
```

## Step 7: Data File Structure

Place data files in the following structure:

```
data/sources/
├── baseball_reference/
│   ├── standard_stats/
│   │   ├── batters_2024.csv
│   │   └── pitchers_2024.csv
│   ├── advanced_stats/
│   │   ├── batters_2024.csv
│   │   └── pitchers_2024.csv
│   └── projections/
│       ├── batters_2025.csv
│       └── pitchers_2025.csv
├── baseball_savant/
│   ├── statcast/
│   │   ├── batters_2024.csv
│   │   └── pitchers_2024.csv
│   └── park_factors/
│       └── park_factors_2024.csv
├── fangraphs/
│   └── projections/
│       ├── steamer_batters_2025.csv
│       ├── steamer_pitchers_2025.csv
│       ├── zips_batters_2025.csv
│       ├── zips_pitchers_2025.csv
│       ├── thebat_batters_2025.csv
│       └── atc_batters_2025.csv
├── rotowire/
│   ├── news/
│   │   └── player_news_2025.json
│   └── injuries/
│       ├── injury_history.csv
│       └── current_injuries.json
├── nfbc/
│   ├── adp/
│   │   └── nfbc_adp_2025.csv
│   └── draft_history/
│       └── nfbc_drafts_2024.json
└── cbs/
    ├── position_eligibility/
    │   └── positions_2025.csv
    ├── historical_drafts/
    │   └── cbs_drafts_2024.json
    └── league_thresholds/
        └── winning_thresholds_2024.json
```

## Step 8: Training Workflow

1. **Collect Data**: Export data from all sources
2. **Load Data**: Use `UnifiedDataMerger` to merge all sources
3. **Extract Features**: Use `FeatureEngineer` for each historical pick
4. **Train Model**: Use `MLTrainer` with historical draft data
5. **Deploy**: Model automatically used in recommendations

## Benefits of This Approach

1. **Real-World Patterns**: Learns from actual draft outcomes
2. **Comprehensive Data**: Uses all available information
3. **Dynamic Weighting**: ADP relevance decreases in later rounds
4. **Risk Assessment**: Factors in injury risk and age
5. **Comparative Advantage**: Maximizes gains vs opponents
6. **Position Scarcity**: Real-time scarcity calculations

## Next Steps

1. Export data from all sources
2. Place files in `data/sources/` directory structure
3. Run data merger to combine all sources
4. Train model on historical draft data
5. Update recommendation engine to use new features

