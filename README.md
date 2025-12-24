# Fantasy Baseball Draft Helper

A local web application to help you dominate your fantasy baseball draft with AI-powered recommendations.

**Configured for: Bob Uecker Imaginary Baseball League**
- 13 teams, 21 active players per team
- Rotisserie scoring (10 categories: HR, OBP, R, RBI, SB, ERA, K, SHOLDS, WHIP, WQS)
- Position requirements: 1 C, 1 1B, 1 2B, 1 3B, 1 SS, 1 MI, 1 CI, 4 OF, 1 U, 9 P
- Pitcher minimums: 1,000-1,400 innings pitched

## 🎯 Features

- **Player Data Management**: Load and store player projections from CSV files
- **Draft Tracking**: Track which players have been drafted to which teams
- **My Team Management**: Keep track of your drafted players with position-based roster slots
- **AI Recommendations**: Get intelligent recommendations based on:
  - Position scarcity analysis
  - Team needs assessment
  - Projected statistical value
  - IP minimum/maximum considerations
  - Category target optimization
- **Auto-Draft**: Automated drafting for non-user teams with tiered strategy:
  - Rounds 1-4: Strict ADP adherence (within 5 picks)
  - Rounds 5-10: Moderate ADP adherence (within 10 picks)
  - Round 11+: AI recommendation engine
- **Projected Standings**: View real-time projected standings with:
  - Category totals and ranks for all teams
  - Roto points calculation (higher = better)
  - IP minimum/maximum enforcement
  - Color-coded category leaders
- **Real-time Updates**: See available players, recent picks, and recommendations update in real-time

## 📁 Project Structure

```
fantasy_baseball_draft_helper/
├── data/                          # Data storage directory
│   ├── teams/                     # Team rosters and draft picks
│   │   └── {team_name}/          # Per-team roster and pick history
│   ├── sources/                   # Source data files
│   │   ├── adp/                  # Average Draft Position data
│   │   ├── projections/          # Player projections
│   │   ├── historical_stats/     # Historical performance data
│   │   └── position_eligibility/ # Position eligibility data
│   ├── league_analysis/          # League analysis and thresholds
│   └── master_players/           # Master player dictionary
│
├── src/                           # Python source code
│   ├── models/                    # Data models
│   │   ├── player.py             # Player data model
│   │   └── draft.py              # Draft state model
│   ├── services/                  # Business logic
│   │   ├── data_loader.py        # CSV loading/saving
│   │   ├── draft_service.py      # Draft management
│   │   ├── recommendation_engine.py # AI recommendation logic
│   │   ├── standings_calculator.py # Rotisserie standings calculation
│   │   └── team_service.py        # Team roster management
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

1. **Load Players**: Players are automatically loaded from the master player dictionary
2. **Create Draft**: Fill in your league details and click "Create/Start Draft"
3. **Get Recommendations**: See AI suggestions in the top status bar
4. **Draft Players**: Click "Draft to My Team" on any available player
5. **Auto-Draft**: Toggle auto-draft for other teams to simulate a full draft
6. **View Standings**: Click "View Standings" to see projected roto standings
7. **Track Progress**: View your team, available players, and recent picks in real-time

## 🤖 AI Recommendation Engine

The recommendation engine analyzes multiple factors to provide intelligent draft suggestions:

1. **Position Scarcity**: How rare is this position among available players?
2. **Team Needs**: Does this player fill a position you need?
3. **Projected Value**: How valuable are this player's projected stats?
4. **IP Considerations**: For pitchers, factors in 1,000-1,400 IP minimum/maximum requirements
5. **Category Targets**: Optimizes for category balance across all 10 roto categories
6. **ADP Value**: Considers average draft position for value picks

Each recommendation includes:
- A numerical score (higher is better)
- Detailed reasoning for the recommendation
- Quick draft button

### Bob Uecker League Scoring Categories

**Batting:** HR, OBP, R, RBI, SB  
**Pitching:** ERA, K, SHOLDS (Saves + Holds x0.5), WHIP, WQS (Wins + Quality Starts)

**Pitcher Requirements:**
- Minimum: 1,000 innings pitched (teams below get zeros in ERA/WHIP)
- Maximum: 1,400 innings pitched (stats capped at limit)

The recommendation engine weights these categories appropriately when calculating player value and considers IP limits when evaluating pitchers.

## 📊 Standings & Scoring

The application calculates projected rotisserie standings based on:
- **Category Totals**: Sum of all player projections for each category
- **Category Rankings**: Teams ranked 1-13 in each category
- **Roto Points**: 1st place = 13 points, 2nd = 12 points, ..., 13th = 1 point
- **Total Points**: Sum across all 10 categories (maximum = 130 points)
- **IP Enforcement**: Teams below 1,000 IP get worst rank in ERA/WHIP; teams above 1,400 IP have stats capped

Standings automatically display when the draft is complete, or you can view them anytime using the "View Standings" button.

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
- **Standings Display**: View projected roto standings with category totals and ranks
- **Auto-Draft Toggle**: Enable/disable automated drafting for other teams
- **Position-Based Roster**: See your team organized by position requirements

## 🔮 Future Enhancements

- Advanced ML models for value prediction
- Custom scoring system configuration
- Draft history and analytics
- Trade suggestions
- Multi-league support
- Export/import draft data
- Player comparison tools

## 📝 Notes

- All data is stored locally on your Mac
- Draft states are auto-saved after each pick
- You can load existing drafts by entering the draft ID
- The app runs entirely locally - no internet required after setup

## 🤝 Contributing

This is a personal project, but feel free to fork and customize for your needs!

## 📄 License

Personal use project - modify as needed.
