"""Flask API for the draft helper application."""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.services.data_loader import DataLoader
from src.services.draft_service import DraftService
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_order import DraftOrder
from src.services.master_player_dict import MasterPlayerDict
from src.models.player import Player
from src.models.draft import DraftState

app = Flask(__name__, 
            template_folder=str(project_root / 'frontend' / 'templates'),
            static_folder=str(project_root / 'frontend' / 'static'))
CORS(app)

# Initialize services
data_loader = DataLoader()
draft_service = DraftService()
recommendation_engine = RecommendationEngine(draft_service)
master_player_dict = MasterPlayerDict()

# Global state (in production, use a database)
all_players: list[Player] = []


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/players/load', methods=['POST'])
def load_players():
    """Load players from CSV file."""
    global all_players
    filename = request.json.get('filename', 'steamer-batters.csv')
    file_type = request.json.get('file_type', 'batters')  # 'batters' or 'pitchers'
    all_players = data_loader.load_players_from_csv(filename, file_type=file_type)
    
    # Check how many players have positions
    players_with_positions = sum(1 for p in all_players if p.position)
    warning = None
    if players_with_positions < len(all_players):
        warning = f'Warning: {len(all_players) - players_with_positions} players are missing position data. Positions are needed for recommendations.'
    
    return jsonify({
        'success': True,
        'count': len(all_players),
        'players_with_positions': players_with_positions,
        'message': f'Loaded {len(all_players)} players',
        'warning': warning
    })


@app.route('/api/players/load-steamer', methods=['POST'])
def load_steamer_files():
    """Load both Steamer hitter and pitcher files and merge projections into master dictionary."""
    global all_players
    
    hitter_file = request.json.get('hitter_file', 'steamer-batters.csv')
    pitcher_file = request.json.get('pitcher_file', 'steamer-pitchers.csv')
    
    # Load Steamer projections
    hitters = data_loader.load_players_from_csv(hitter_file, file_type='batters')
    pitchers = data_loader.load_players_from_csv(pitcher_file, file_type='pitchers')
    
    # Merge Steamer projections into master dictionary
    master_player_dict.merge_steamer_projections(hitters, player_type='batters')
    master_player_dict.merge_steamer_projections(pitchers, player_type='pitchers')
    
    # Load and merge ADP data
    master_player_dict.load_adp_data()
    
    # Get players with merged projections (CBS base + Steamer projections + ADP)
    all_players = (
        master_player_dict.get_players_with_projections(player_type='batters') +
        master_player_dict.get_players_with_projections(player_type='pitchers')
    )
    
    # If no CBS data loaded yet, use Steamer directly
    if not all_players:
        all_players = hitters + pitchers
    
    players_with_positions = sum(1 for p in all_players if p.position)
    hitters_count = len(hitters)
    pitchers_count = len(pitchers)
    
    warning = None
    if players_with_positions < len(all_players):
        warning = f'Warning: {len(all_players) - players_with_positions} players are missing position data. Positions are needed for recommendations.'
    
    return jsonify({
        'success': True,
        'count': len(all_players),
        'hitters': hitters_count,
        'pitchers': pitchers_count,
        'players_with_positions': players_with_positions,
        'message': f'Merged Steamer projections: {hitters_count} hitters and {pitchers_count} pitchers. {len(all_players)} players available with projections.',
        'warning': warning
    })


@app.route('/api/players/load-cbs', methods=['POST'])
def load_cbs_data():
    """Load CBS data (source of truth for available players) and merge with projections."""
    global all_players
    
    hitter_file = request.json.get('hitter_file', 'cbs-batter-2025.csv')
    pitcher_file = request.json.get('pitcher_file', 'cbs-pitchers-2025.csv')
    
    # Load CBS data
    hitters = data_loader.load_players_from_csv(hitter_file, file_type='batters')
    pitchers = data_loader.load_players_from_csv(pitcher_file, file_type='pitchers')
    
    # Merge CBS data into master dictionary (source of truth for available players)
    master_player_dict.merge_cbs_data(hitters, player_type='batters')
    master_player_dict.merge_cbs_data(pitchers, player_type='pitchers')
    
    # Load and merge ADP data
    master_player_dict.load_adp_data()
    
    # Get players with merged projections (CBS base + any existing projections + ADP)
    all_players = (
        master_player_dict.get_players_with_projections(player_type='batters') +
        master_player_dict.get_players_with_projections(player_type='pitchers')
    )
    
    players_with_positions = sum(1 for p in all_players if p.position)
    
    return jsonify({
        'success': True,
        'count': len(all_players),
        'hitters': len(hitters),
        'pitchers': len(pitchers),
        'players_with_positions': players_with_positions,
        'message': f'Loaded CBS data: {len(hitters)} hitters and {len(pitchers)} pitchers. {len(all_players)} total players available to draft.'
    })


@app.route('/api/players', methods=['GET'])
def get_players():
    """Get all players from master dictionary (CBS base + merged projections), sorted by ADP."""
    global all_players
    
    # Try to get players from master dictionary if available
    try:
        merged_players = (
            master_player_dict.get_players_with_projections(player_type='batters') +
            master_player_dict.get_players_with_projections(player_type='pitchers')
        )
        if merged_players:
            all_players = merged_players
    except:
        pass  # Fall back to all_players if master dict not available
    
    # Sort by ADP (lower is better, None values go to end)
    sorted_players = sorted(
        all_players,
        key=lambda p: (p.adp is None, p.adp or float('inf'))
    )
    
    return jsonify({
        'players': [p.to_dict() for p in sorted_players]
    })


@app.route('/api/draft/create', methods=['POST'])
def create_draft():
    """Create a new draft."""
    data = request.json
    my_team_name = data.get('my_team_name', 'My Team')
    
    # Validate my_team_name is in the list of teams
    all_teams = DraftOrder.get_all_teams()
    if my_team_name not in all_teams:
        # Default to first team if not specified
        my_team_name = all_teams[0]
    
    draft = draft_service.create_draft(
        draft_id=data.get('draft_id', f"draft_{int(__import__('time').time())}"),
        league_name=data.get('league_name', 'Bob Uecker League'),
        total_teams=data.get('total_teams', 13),
        roster_size=data.get('roster_size', 21),
        my_team_name=my_team_name
    )
    return jsonify({
        'success': True,
        'draft': draft.to_dict()
    })


@app.route('/api/draft/load', methods=['POST'])
def load_draft():
    """Load an existing draft."""
    draft_id = request.json.get('draft_id')
    draft = draft_service.load_draft(draft_id)
    if draft:
        return jsonify({
            'success': True,
            'draft': draft.to_dict()
        })
    return jsonify({
        'success': False,
        'message': 'Draft not found'
    }), 404


@app.route('/api/draft/current', methods=['GET'])
def get_current_draft():
    """Get current draft state."""
    if draft_service.current_draft:
        return jsonify({
            'success': True,
            'draft': draft_service.current_draft.to_dict()
        })
    return jsonify({
        'success': False,
        'message': 'No active draft'
    }), 404


@app.route('/api/draft/pick', methods=['POST'])
def make_pick():
    """Make a draft pick."""
    data = request.json
    player_id = data['player_id']
    
    # Determine which team should pick based on draft order
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    pick_number = len(draft_service.current_draft.picks) + 1
    team_name = DraftOrder.get_team_for_pick(pick_number, draft_service.current_draft.total_teams)
    
    # Find the player object
    player = next((p for p in all_players if p.player_id == player_id), None)
    
    success = draft_service.draft_player(
        player_id=player_id,
        team_name=team_name,
        player=player
    )
    if success:
        return jsonify({
            'success': True,
            'draft': draft_service.current_draft.to_dict()
        })
    return jsonify({
        'success': False,
        'message': 'Failed to make pick'
    }), 400


@app.route('/api/draft/available', methods=['GET'])
def get_available_players():
    """Get available (undrafted) players, sorted by ADP."""
    available = draft_service.get_available_players(all_players)
    # Sort by ADP (lower is better, None values go to end)
    sorted_available = sorted(
        available,
        key=lambda p: (p.adp is None, p.adp or float('inf'))
    )
    return jsonify({
        'players': [p.to_dict() for p in sorted_available]
    })


@app.route('/api/draft/my-team', methods=['GET'])
def get_my_team():
    """Get my team's players."""
    my_team = draft_service.get_my_team_players(all_players)
    return jsonify({
        'players': [p.to_dict() for p in my_team]
    })


@app.route('/api/draft/team/<team_name>', methods=['GET'])
def get_team(team_name):
    """Get a specific team's players."""
    team_players = draft_service.get_team_players(all_players, team_name)
    return jsonify({
        'players': [p.to_dict() for p in team_players]
    })


@app.route('/api/draft/team/<team_name>/roster', methods=['GET'])
def get_team_roster(team_name):
    """Get a specific team's roster with position structure."""
    from src.services.team_service import TeamService
    team_service = TeamService()
    roster = team_service.get_team_roster(team_name)
    return jsonify({
        'roster': roster
    })


@app.route('/api/draft/revert', methods=['POST'])
def revert_pick():
    """Revert/undo a draft pick."""
    data = request.json
    pick_number = data.get('pick_number')
    
    if not pick_number:
        return jsonify({
            'success': False,
            'message': 'pick_number is required'
        }), 400
    
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    success = draft_service.revert_pick(pick_number)
    
    if success:
        return jsonify({
            'success': True,
            'draft': draft_service.current_draft.to_dict()
        })
    
    return jsonify({
        'success': False,
        'message': 'Failed to revert pick'
    }), 400


@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get AI recommendations for next pick."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    available = draft_service.get_available_players(all_players)
    my_team = draft_service.get_my_team_players(all_players)
    
    recommendations = recommendation_engine.get_recommendations(
        available_players=available,
        my_team=my_team,
        draft_state=draft_service.current_draft,
        top_n=10
    )
    
    return jsonify({
        'recommendations': [
            {
                'player': rec['player'].to_dict(),
                'score': rec['score'],
                'reasoning': rec['reasoning']
            }
            for rec in recommendations
        ]
    })


if __name__ == '__main__':
    app.run(debug=True, port=5001)

