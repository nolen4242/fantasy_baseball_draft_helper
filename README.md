# Fantasy Baseball Draft Helper

A local web application to help you dominate your fantasy baseball draft with AI-powered recommendations.

**Configured for: Bob Uecker Imaginary Baseball League**
- 13 teams, 21 active players per team
- Rotisserie scoring
- Position requirements: 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P

## 🎯 Features

- **Player Data Management**: Load and store player projections from CSV files
- **Draft Tracking**: Track which players have been drafted to which teams
- **My Team Management**: Keep track of your drafted players
- **AI Recommendations**: Get intelligent recommendations based on:
  - Standings improvement (primary metric)
  - Roster balance and IP accumulation
  - ML model predictions
  - Position scarcity analysis
  - Team needs assessment
  - Future availability prediction
  - Category targeting
  - Relative advantage vs opponents
  - Risk assessment
- **Configurable Scoring**: Customize recommendation weights and switch between strategy profiles
- **Transparent Scoring**: See detailed breakdowns of why each player is recommended
- **Real-time Updates**: See available players, recent picks, and recommendations update in real-time

## 📁 Project Structure

```
fantasy_baseball_draft_helper/
├── config/                        # Configuration files
│   └── scoring/                   # Scoring profile configurations
│       ├── default.json          # Default balanced profile
│       ├── aggressive.json       # Aggressive value-seeking
│       ├── conservative.json     # Conservative safe picks
│       ├── pitcher_heavy.json    # Pitcher-focused strategy
│       └── hitter_heavy.json     # Hitter-focused strategy
│
├── data/                          # Data storage directory
│   ├── players/                   # Player projection CSV files
│   │   ├── projections.csv        # Your main player data file
│   │   └── example_projections.csv # Example file with sample data
│   └── drafts/                    # Draft state files (auto-generated)
│       └── {draft_id}.json        # Saved draft states
│
├── src/                           # Python source code
│   ├── models/                    # Data models
│   │   ├── player.py             # Player data model
│   │   └── draft.py              # Draft state model
│   ├── services/                  # Business logic
│   │   ├── data_loader.py        # CSV loading/saving
│   │   ├── draft_service.py      # Draft management
│   │   ├── recommendation_engine.py # AI recommendation logic
│   │   ├── scoring_config.py     # Scoring configuration management
│   │   ├── scoring_breakdown.py  # Transparent scoring breakdowns
│   │   └── config_manager.py     # Profile management
│   └── api/                       # Web API
│       └── app.py                # Flask application
│
├── frontend/                      # Web UI
│   ├── templates/                 # HTML templates
│   │   └── index.html            # Main page
│   └── static/                    # Static assets
│       ├── css/
│       │   └── style.css         # Styling
│       └── js/
│           └── app.js            # Frontend logic
│
├── ml/                            # Machine learning (future expansion)
│   ├── models/                    # Trained ML models
│   └── training/                  # Training scripts
│
├── .kiro/specs/                   # Feature specifications
│   └── recommendation-engine-improvements/
│       ├── requirements.md        # Feature requirements
│       ├── design.md             # Technical design
│       ├── tasks.md              # Implementation tasks
│       └── SCORING_GUIDE.md      # Detailed scoring documentation
│
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## 🛠️ Technology Stack

### Backend
- **Python 3.8+**: Core programming language
- **Flask**: Lightweight web framework for the API
- **NumPy/Pandas**: Data manipulation and analysis
- **scikit-learn**: Machine learning capabilities (for future enhancements)

### Frontend
- **HTML5/CSS3**: Modern, responsive UI
- **Vanilla JavaScript**: No framework dependencies, fast and lightweight
- **Modern CSS Grid/Flexbox**: Beautiful, responsive layout

### Data Storage
- **CSV Files**: Player projections (easy to import from various sources)
- **JSON Files**: Draft state persistence (auto-saved)

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Your Player Data

Place your player projection CSV file in `data/players/`. The CSV should include columns like:
- `name`, `position`, `team`, `age`
- Projected stats: `projected_home_runs`, `projected_runs`, `projected_rbi`, etc.
- Or use common abbreviations: `hr`, `r`, `rbi`, `sb`, `avg`, `w`, `k`, `era`, `whip`, `sv`

See `data/players/example_projections.csv` for a sample format.

### 3. Run the Application

```bash
python src/api/app.py
```

The application will start on `http://localhost:5000`

### 4. Use the Application

1. **Load Players**: Enter your CSV filename and click "Load Players"
2. **Create Draft**: Fill in your league details and click "Create/Start Draft"
3. **Get Recommendations**: Click "Refresh Recommendations" to see AI suggestions
4. **Draft Players**: Click "Draft to My Team" on any available player
5. **Track Progress**: View your team, available players, and recent picks

## 🤖 AI Recommendation Engine

The recommendation engine uses a sophisticated multi-factor scoring system to evaluate players and provide intelligent draft recommendations.

### Configuration & Profiles

The recommendation engine is now fully configurable! You can adjust scoring weights and switch between different strategy profiles to match your draft approach.

**Available Profiles:**
- **Default**: Balanced scoring for most situations
- **Aggressive**: Value-seeking strategy (higher ML weight, lower risk penalties)
- **Conservative**: Safe picks prioritizing team needs (higher position needs, higher risk penalties)
- **Pitcher Heavy**: Prioritizes pitchers and IP accumulation
- **Hitter Heavy**: Prioritizes hitters and offensive categories

**Using the Config API:**

```bash
# Get current configuration
curl http://localhost:5000/api/recommendations/config

# List available profiles
curl http://localhost:5000/api/recommendations/config/profiles

# Switch to aggressive profile
curl -X POST http://localhost:5000/api/recommendations/config/profile \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "aggressive"}'

# Update specific weights
curl -X PATCH http://localhost:5000/api/recommendations/config \
  -H "Content-Type: application/json" \
  -d '{"standings_multiplier": 35.0, "ml_multiplier": 5.0}'

# Reset to default
curl -X POST http://localhost:5000/api/recommendations/config/reset
```

**Custom Profiles:**

You can create custom profiles by editing JSON files in `config/scoring/`:

```json
{
  "profile_name": "my_custom",
  "description": "My custom strategy",
  "version": "1.0",
  "standings_multiplier": 30.0,
  "ml_multiplier": 3.0,
  ...
}
```

See `.kiro/specs/recommendation-engine-improvements/SCORING_GUIDE.md` for detailed explanations of all scoring factors and weights.

### Core Scoring Factors

1. **Standings Improvement** (30x multiplier): Calculates actual standings points gained
2. **Roster Balance**: Ensures you meet IP minimums and fill your lineup
3. **ML Model Prediction** (3x multiplier): Machine learning trained on historical drafts
4. **Future Availability**: Predicts if player will be available at your next pick
5. **Team Needs**: Identifies gaps in your roster
6. **Position Scarcity**: Values positions running out of quality players
7. **Category Targeting**: Prioritizes categories where you're behind
8. **Relative Advantage**: Analyzes how player helps vs opponents
9. **Risk Assessment**: Reduces score for injury-prone or unreliable players

Each recommendation includes:
- A numerical score (higher is better)
- Detailed reasoning for the recommendation
- Quick draft button

**For detailed scoring explanations**, see:
- `.kiro/specs/recommendation-engine-improvements/SCORING_GUIDE.md` - Complete scoring factor documentation
- `.kiro/specs/recommendation-engine-improvements/design.md` - Technical architecture and design

### Bob Uecker League Scoring Categories

**Batting:** HR, OBP, R, RBI, SB  
**Pitching:** ERA, K, SHOLDS (Saves + Holds x0.5), WHIP, WQS (Wins + Quality Starts)

The recommendation engine weights these categories appropriately when calculating player value.

## 📊 CSV File Format

Your player projection CSV should have these columns (flexible naming):

**Required:**
- `name` or `player_name`
- `position` (e.g., "OF", "1B", "SP", "RP", "MI", "CI", "U")
- `team` (team abbreviation)

**Optional but Recommended:**
- `age`

**Batting Categories (Bob Uecker League):**
- `projected_home_runs` (or `hr`)
- `projected_obp` (or `obp`) - On Base Percentage
- `projected_runs` (or `r`)
- `projected_rbi` (or `rbi`)
- `projected_stolen_bases` (or `sb`)

**Pitching Categories (Bob Uecker League):**
- `projected_wins` (or `w`)
- `projected_quality_starts` (or `qs`) - Quality Starts
- `projected_strikeouts` (or `k`/`so`)
- `projected_era` (or `era`)
- `projected_whip` (or `whip`)
- `projected_saves` (or `sv`)
- `projected_holds` (or `hld`/`holds`)

See `data/players/example_projections.csv` for a sample format.

## 🎨 UI Features

- **Responsive Design**: Works on desktop and tablet
- **Real-time Updates**: See changes immediately after drafting
- **Search & Filter**: Find players by name or filter by position
- **Visual Feedback**: Color-coded recommendations and player cards
- **Draft Status**: Always see current round, pick, and total picks

## 🔮 Future Enhancements

- ✅ **Custom scoring system configuration** - COMPLETED
- ✅ **Transparent scoring breakdowns** - COMPLETED
- Advanced ML models for value prediction
- Draft history and analytics
- Trade suggestions
- Multi-league support
- Export/import draft data
- Player comparison tools
- UI for config management (currently API-only)

## 📝 Notes

- All data is stored locally on your Mac
- Draft states are auto-saved after each pick
- You can load existing drafts by entering the draft ID
- The app runs entirely locally - no internet required after setup

## 🤝 Contributing

This is a personal project, but feel free to fork and customize for your needs!

## 📄 License

Personal use project - modify as needed.
