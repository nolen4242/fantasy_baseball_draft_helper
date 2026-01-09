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
  - Position scarcity analysis
  - Team needs assessment
  - Projected statistical value
- **Real-time Updates**: See available players, recent picks, and recommendations update in real-time

## 📁 Project Structure

```
fantasy_baseball_draft_helper/
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
│   │   └── recommendation_engine.py # AI recommendation logic
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

1. **Load Players**: Enter your CSV filename and click "Load Players"
2. **Create Draft**: Fill in your league details and click "Create/Start Draft"
3. **Get Recommendations**: Click "Refresh Recommendations" to see AI suggestions
4. **Draft Players**: Click "Draft to My Team" on any available player
5. **Track Progress**: View your team, available players, and recent picks

## 🤖 AI Recommendation Engine

The recommendation engine analyzes three key factors:

1. **Position Scarcity** (30% weight): How rare is this position among available players?
2. **Team Needs** (30% weight): Does this player fill a position you need?
3. **Projected Value** (40% weight): How valuable are this player's projected stats?

Each recommendation includes:
- A numerical score (higher is better)
- Detailed reasoning for the recommendation
- Quick draft button

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
