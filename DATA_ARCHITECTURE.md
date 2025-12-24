# Data Architecture - Complete Guide

## Overview

All raw data goes into `raw/` folder, then gets processed, merged, and cleaned into `data/` folder. The architecture is organized by **DATA TYPE**, not vendor. Each data type can have multiple sources merged together.

## Core Principle: One Master File

**For the app**: Use ONE master file with everything merged  
**For processing**: Keep sources separate by data type for debugging/flexibility  
**Best of both worlds**: Simple for app, flexible for data pipeline

## Directory Structure

### Raw Data (`raw/`)

#### Current Season Data
```
raw/
├── cbs_catchers_2025_stats.csv    # Position eligibility + current projections
├── cbs_1b_2025_stats.csv
├── cbs_2b_2025_stats.csv
├── cbs_3b_2025_stats.csv
├── cbs_ss_2025_stats.csv
├── cbs_of_2025_stats.csv
└── cbs_pitchers_2025_stats.csv
```

#### Historical Data (`raw/historical_data/`)
```
raw/historical_data/
├── historical_stats/        # Past player stats (from multiple sources)
│   ├── bbref_2024_stats.csv
│   ├── fangraphs_2024_stats.csv
│   ├── savant_2024_statcast.csv
│   └── ...
│
├── projections/            # Historical projections (from multiple sources)
│   ├── steamer_2024.csv
│   ├── zips_2024.csv
│   ├── the_bat_2024.csv
│   └── ...
│
├── park_factors/           # Park factor data (from multiple sources)
│   ├── savant_2024_park_factors.csv
│   ├── fangraphs_2024_park_factors.csv
│   └── ...
│
├── player_info/            # News, injuries, contracts (from multiple sources)
│   ├── rotowire_2024_injuries.csv
│   ├── rotowire_2024_news.csv
│   ├── cbs_2024_news.csv
│   └── ...
│
├── adp/                    # ADP data (from multiple sources)
│   ├── nfbc_2024_adp.csv
│   ├── cbs_2024_adp.csv
│   ├── espn_2024_adp.csv
│   └── ...
│
└── cbs_winners/           # CBS league winners (historical)
    ├── 2024_winners.csv
    ├── 2023_winners.csv
    └── ...
```

### Processed Data (`data/`)

#### Sources (`data/sources/`) - By Data Type
**Purpose**: Processed data by type (for debugging/reference only)  
**Note**: App doesn't use these - they're for processing pipeline

```
data/sources/
├── position_eligibility/    # Player positions (from CBS, etc.)
│   ├── players.json        # All players with position eligibility
│   └── metadata.json
│
├── historical_stats/        # Past performance (from BBRef, Fangraphs, Savant)
│   ├── players.json        # All players with historical stats
│   └── metadata.json
│
├── projections/            # Projections (from Steamer, ZiPS, THE BAT, etc.)
│   ├── players.json        # All players with projections
│   └── metadata.json
│
├── park_factors/           # Park factors (from Savant, Fangraphs)
│   ├── parks.json          # All parks with factors
│   └── metadata.json
│
├── player_info/            # News, injuries, contracts (from Rotowire, CBS, etc.)
│   ├── players.json        # All players with news/injury data
│   └── metadata.json
│
└── adp/                    # ADP data (from NFBC, CBS, ESPN, etc.)
    ├── players.json        # All players with ADP
    └── metadata.json
```

#### Master Players (`data/master_players/`)
**Purpose**: ONE FILE per player type with everything merged  
**Note**: This is what the app uses - single source of truth

```
data/master_players/
├── hitters.json            # All hitter data merged
│   └── Contains: position, historical stats, projections, ADP, risk, news, park factors, etc.
│
├── pitchers.json           # All pitcher data merged
│   └── Contains: position, historical stats, projections, ADP, risk, news, park factors, etc.
│
└── metadata.json           # Version, last updated, sources used
```

#### League Analysis (`data/league_analysis/`)
**Purpose**: Analysis of what it takes to win  
**Note**: Completely separate from master player dict - this is league-level analysis

```
data/league_analysis/
├── cbs_winners.json        # Historical winning teams (from raw/historical_data/cbs_winners/)
│   └── Contains: rosters, category totals, draft positions
│
├── category_thresholds.json # What it takes to win each category
│   └── Example: "HR: 350+ to win, 300+ to compete"
│
└── optimal_rosters.json     # Ideal category balance
    └── Example: "Winning teams have X HR, Y SB, Z K, etc."
```

#### Teams (`data/teams/`)
**Purpose**: Draft tracking (KEEP - untouched)

```
data/teams/
├── Runtime_Terror/
│   └── roster.json
├── draft_*.json
└── ...
```

## Data Types

### 1. Position Eligibility
- **Sources**: CBS (primary), Baseball Reference, Fangraphs
- **Contains**: Name, position, position eligibility, team
- **Purpose**: Foundation for all player matching

### 2. Historical Stats
- **Sources**: Baseball Reference, Fangraphs, Baseball Savant
- **Contains**: Past 3-5 years of stats (standard, advanced, Statcast)
- **Purpose**: Performance trends, aging curves

### 3. Projections
- **Sources**: Steamer, ZiPS, THE BAT, ATC, BB Forecaster
- **Contains**: Projected stats for current season
- **Purpose**: Primary input for value calculations

### 4. Park Factors
- **Sources**: Baseball Savant, Fangraphs
- **Contains**: HR factor, run factor, etc. for each ballpark
- **Purpose**: Adjust projections based on home park

### 5. Player Info
- **Sources**: Rotowire, CBS, news aggregators
- **Contains**: Injuries, news, trades, contracts
- **Purpose**: Risk assessment, opportunity identification

### 6. ADP
- **Sources**: NFBC, CBS, ESPN, Yahoo
- **Contains**: Average draft position from multiple sources
- **Purpose**: Market value, draft strategy

### 7. CBS Winners (Separate - League Analysis)
- **Source**: CBS league data from prior years
- **Contains**: Winning team rosters, category totals
- **Purpose**: Determine winning thresholds, optimal category balance
- **Note**: NOT merged into master player dict - processed separately into league_analysis/

## Data Flow

```
1. Raw Data (by type)
   raw/cbs_*.csv → Position eligibility + current projections
   raw/historical_data/historical_stats/*.csv → Historical stats
   raw/historical_data/projections/*.csv → Projections
   raw/historical_data/cbs_winners/*.csv → CBS winners

2. Process by Type
   raw/ → Process → data/sources/position_eligibility/players.json
   raw/historical_data/historical_stats/* → Process → data/sources/historical_stats/players.json
   raw/historical_data/projections/* → Process → data/sources/projections/players.json

3. Merge into Master (Player Data Only)
   data/sources/position_eligibility/* → Match & Merge → data/master_players/hitters.json
   data/sources/historical_stats/* → Match & Merge → data/master_players/hitters.json
   data/sources/projections/* → Match & Merge → data/master_players/hitters.json
   data/sources/adp/* → Match & Merge → data/master_players/hitters.json
   data/sources/player_info/* → Match & Merge → data/master_players/hitters.json
   data/sources/park_factors/* → Match & Merge → data/master_players/hitters.json

4. Process League Analysis (Separate from Player Data)
   raw/historical_data/cbs_winners/* → Process → data/league_analysis/cbs_winners.json
   data/league_analysis/cbs_winners.json → Analyze → data/league_analysis/category_thresholds.json
   data/league_analysis/cbs_winners.json → Analyze → data/league_analysis/optimal_rosters.json

5. App Uses Data
   App reads: data/master_players/hitters.json (player data)
   App reads: data/master_players/pitchers.json (player data)
   App reads: data/league_analysis/*.json (league analysis - separate)
```

## Master File Structure

```json
{
  "metadata": {
    "version": "2025.1",
    "last_updated": "2025-01-XX",
    "sources": ["cbs", "bbref", "fangraphs", "savant", "steamer", "zips"],
    "player_count": 2000
  },
  "players": [
    {
      "unified_id": "unified_aaron_judge",
      "name": "Aaron Judge",
      "normalized_name": "aaron judge",
      
      // Position & Team (from position_eligibility)
      "position": "OF",
      "position_eligibility": ["OF"],
      "team": "NYY",
      "park": "Yankee Stadium",
      "park_factors": { "hr_factor": 1.15 },
      
      // Historical Stats (from historical_stats)
      "historical_stats": {
        "2024": { "hr": 62, "rbi": 131, "wrc_plus": 174 },
        "2023": { "hr": 37, "rbi": 75, "wrc_plus": 174 }
      },
      
      // Projections (from projections) - MERGED
      "projections": {
        "steamer": { "hr": 53, "rbi": 114 },
        "zips": { "hr": 50, "rbi": 110 },
        "consensus": { "hr": 52, "rbi": 112 }  // Weighted average
      },
      
      // ADP (from adp) - MERGED
      "adp": {
        "nfbc": 1.2,
        "cbs": 1.5,
        "composite": 1.35
      },
      "custom_adp": 1.5,  // League-specific
      
      // Risk & News (from player_info)
      "risk": {
        "injury_risk": "moderate",
        "recent_injuries": [...]
      },
      "news": [
        { "date": "2025-01-15", "type": "trade", "content": "..." }
      ],
      
      // Derived Metrics (calculated)
      "value_score": 95.5,
      "risk_adjusted_value": 92.3
    }
  ]
}
```

## Key Features

### 1. Multi-Position Player Handling
- Players can appear in multiple position files (e.g., "Ben Rice C,1B")
- System automatically merges duplicates and tracks all position eligibility

### 2. Intelligent Name Matching
- Handles name variations (Nate vs Nathan, Mike vs Michael, etc.)
- Normalizes names (removes accents, suffixes, punctuation)
- Uses fuzzy matching for cross-database matching
- Confidence scoring (0.0 to 1.0) for match quality

### 3. Data Cleaning & Validation
- Validates required fields
- Checks for outliers (unusual stat values)
- Calculates data completeness scores
- Flags data quality issues

### 4. Cross-Database Matching
- Finds potential matches across different data sources
- Auto-confirms high-confidence matches (>= 0.95)
- Requires confirmation for medium-confidence matches (0.85-0.95)
- Stores confirmed and pending matches

## File Naming Conventions

### Raw Files
- `{source}_{year}_{type}.csv`
- Example: `bbref_2024_stats.csv`, `steamer_2024_projections.csv`

### Processed Source Files
- `players.json` - Player data of this type
- `metadata.json` - Source metadata

### Master Files
- `hitters.json` - All hitter data merged (all types)
- `pitchers.json` - All pitcher data merged (all types)
- `metadata.json` - Master metadata

## Benefits

1. ✅ **Single Call**: App reads one master file
2. ✅ **Fast**: One file I/O, no merging at runtime
3. ✅ **Simple**: One structure, easy to understand
4. ✅ **Debuggable**: Can still check individual sources if needed
5. ✅ **Maintainable**: Clear separation: raw → sources → master
6. ✅ **Flexible**: Can reprocess individual sources
7. ✅ **Source Attribution**: Master file includes source info

## Implementation Status

- ✅ Directory structure created
- ⏳ CBS data loader (raw/ → sources/position_eligibility/)
- ⏳ CBS winners analyzer (raw/historical_data/cbs_winners/ → league_analysis/)
- ⏳ Master merger (sources/* → master_players/)
- ⏳ Category threshold calculator (from winners data)
