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
from src.services.ml_trainer import MLTrainer
from src.models.player import Player
from src.models.draft import DraftState

app = Flask(__name__, 
            template_folder=str(project_root / 'frontend' / 'templates'),
            static_folder=str(project_root / 'frontend' / 'static'))
CORS(app)

# Initialize services
data_loader = DataLoader()
draft_service = DraftService()
master_player_dict = MasterPlayerDict()

# Global state (in production, use a database)
all_players: list[Player] = []

# Initialize recommendation engine (will be updated when players are loaded)
recommendation_engine = RecommendationEngine(draft_service, all_players)


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
    
    # Update recommendation engine with new players
    recommendation_engine.all_players = all_players
    
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
    
    # Update recommendation engine with new players
    recommendation_engine.all_players = all_players
    
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
    requested_team_name = data.get('team_name')  # Team name from request (for manual picks)
    
    # Determine which team should pick based on draft order
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    pick_number = len(draft_service.current_draft.picks) + 1
    draft_order_team = DraftOrder.get_team_for_pick(pick_number, draft_service.current_draft.total_teams)
    
    # Use requested team name if provided (for manual picks), otherwise use draft order
    team_name = requested_team_name if requested_team_name else draft_order_team
    
    # Check if this team's roster is already full
    team_roster_size = len(draft_service.current_draft.team_rosters.get(team_name, []))
    if team_roster_size >= draft_service.current_draft.roster_size:
        # Even if roster is full, allow drafting if required positions aren't filled
        from src.services.team_service import TeamService
        team_service = TeamService()
        roster = team_service.get_team_roster(team_name)
        if roster and 'positions' in roster:
            # Check if any required position is empty
            required_positions = TeamService.POSITION_REQUIREMENTS
            has_unfilled_position = False
            for pos, required_count in required_positions.items():
                if pos == 'BENCH':  # Skip bench - it's optional
                    continue
                filled_count = sum(1 for slot in roster['positions'].get(pos, []) if slot is not None)
                if filled_count < required_count:
                    has_unfilled_position = True
                    break
            
            if not has_unfilled_position:
                return jsonify({
                    'success': False,
                    'message': f'{team_name} roster is full and all required positions are filled'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': f'{team_name} roster is full ({team_roster_size}/{draft_service.current_draft.roster_size} players)'
            }), 400
    
    # Find the player object
    player = next((p for p in all_players if p.player_id == player_id), None)
    
    if not player:
        return jsonify({
            'success': False,
            'message': 'Player not found'
        }), 404
    
    success = draft_service.draft_player(
        player_id=player_id,
        team_name=team_name,
        player=player
    )
    if success:
        draft_dict = draft_service.current_draft.to_dict()
        return jsonify({
            'success': True,
            'draft': draft_dict,
            'draft_complete': draft_dict.get('is_complete', False)
        })
    
    return jsonify({
        'success': False,
        'message': 'Failed to make pick - roster may be full or draft complete'
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
    """Get my team's players and roster structure."""
    if not draft_service.current_draft:
        return jsonify({
            'players': [],
            'roster': None
        }), 404
    
    my_team = draft_service.get_my_team_players(all_players)
    from src.services.team_service import TeamService
    team_service = TeamService()
    roster = team_service.get_team_roster(draft_service.current_draft.my_team_name)
    
    return jsonify({
        'players': [p.to_dict() for p in my_team],
        'roster': roster
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


@app.route('/api/draft/cleanup-duplicates', methods=['POST'])
def cleanup_duplicate_players():
    """Clean up duplicate player entries in a team's roster."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    data = request.json or {}
    team_name = data.get('team_name', draft_service.current_draft.my_team_name)
    
    from src.services.team_service import TeamService
    team_service = TeamService()
    
    try:
        team_service.cleanup_duplicate_players(team_name)
        roster = team_service.get_team_roster(team_name)
        return jsonify({
            'success': True,
            'roster': roster,
            'message': f'Cleaned up duplicate players for {team_name}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error cleaning up duplicates: {str(e)}'
        }), 500


@app.route('/api/draft/move-player', methods=['POST'])
def move_player_position():
    """Move a player from one position slot to another."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    data = request.json
    player_id = data.get('player_id')
    from_position = data.get('from_position')
    from_index = data.get('from_index')
    to_position = data.get('to_position')
    to_index = data.get('to_index')
    team_name = data.get('team_name', draft_service.current_draft.my_team_name)
    
    if not all([player_id, from_position is not None, from_index is not None, 
                to_position is not None, to_index is not None]):
        return jsonify({
            'success': False,
            'message': 'Missing required parameters'
        }), 400
    
    from src.services.team_service import TeamService
    team_service = TeamService()
    
    # Get the player
    player = next((p for p in all_players if p.player_id == player_id), None)
    if not player:
        return jsonify({
            'success': False,
            'message': 'Player not found'
        }), 404
    
    # Check if player is eligible for target position
    eligible_positions = team_service._determine_eligible_positions(player)
    if to_position not in eligible_positions:
        return jsonify({
            'success': False,
            'message': f'Player is not eligible for {to_position} position'
        }), 400
    
    # Move the player
    success = team_service.move_player_position(
        team_name=team_name,
        player_id=player_id,
        from_position=from_position,
        from_index=from_index,
        to_position=to_position,
        to_index=to_index
    )
    
    if success:
        roster = team_service.get_team_roster(team_name)
        return jsonify({
            'success': True,
            'roster': roster
        })
    
    return jsonify({
        'success': False,
        'message': 'Failed to move player'
    }), 400


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


@app.route('/api/draft/restart', methods=['POST'])
def restart_draft():
    """Completely restart the draft - clears all picks and resets all team rosters."""
    from src.services.cleanup_service import CleanupService
    
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    # Clean up all team rosters
    cleanup = CleanupService()
    cleanup.cleanup_all_team_rosters()
    
    # Reset the draft state
    draft_id = draft_service.current_draft.draft_id
    league_name = draft_service.current_draft.league_name
    total_teams = draft_service.current_draft.total_teams
    roster_size = draft_service.current_draft.roster_size
    my_team_name = draft_service.current_draft.my_team_name
    
    # Create a fresh draft with the same settings
    new_draft = draft_service.create_draft(
        draft_id=draft_id,
        league_name=league_name,
        total_teams=total_teams,
        roster_size=roster_size,
        my_team_name=my_team_name
    )
    
    return jsonify({
        'success': True,
        'draft': new_draft.to_dict(),
        'message': 'Draft restarted - all picks cleared'
    })


@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get AI recommendations for next pick."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    # Update recommendation engine with current players
    recommendation_engine.all_players = all_players
    
    available = draft_service.get_available_players(all_players)
    my_team = draft_service.get_my_team_players(all_players)
    
    use_ml = request.args.get('use_ml', 'true').lower() == 'true'
    
    recommendations = recommendation_engine.get_recommendations(
        available_players=available,
        my_team=my_team,
        draft_state=draft_service.current_draft,
        top_n=10,
        use_ml=use_ml
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


@app.route('/api/draft/auto-draft/toggle', methods=['POST'])
def toggle_auto_draft():
    """Toggle auto-draft mode on/off."""
    data = request.json or {}
    enabled = data.get('enabled', False)
    
    draft_service.set_auto_draft(enabled)
    
    return jsonify({
        'success': True,
        'auto_draft_enabled': draft_service.is_auto_draft_enabled(),
        'message': f'Auto-draft {"enabled" if enabled else "disabled"}'
    })


@app.route('/api/draft/auto-draft/status', methods=['GET'])
def get_auto_draft_status():
    """Get current auto-draft status."""
    return jsonify({
        'auto_draft_enabled': draft_service.is_auto_draft_enabled()
    })


@app.route('/api/draft/auto-draft/pick', methods=['POST'])
def make_auto_draft_pick():
    """Make an auto-draft pick for a team using AI recommendations."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400
    
    # Check if draft is already complete
    if draft_service.current_draft.is_draft_complete():
        return jsonify({
            'success': False,
            'message': 'Draft is complete - all roster spots are filled'
        }), 400
    
    data = request.json or {}
    team_name = data.get('team_name')
    
    if not team_name:
        return jsonify({
            'success': False,
            'message': 'team_name is required'
        }), 400
    
    # Don't auto-draft for the user's team
    if team_name == draft_service.current_draft.my_team_name:
        return jsonify({
            'success': False,
            'message': 'Cannot auto-draft for your own team'
        }), 400
    
    # Check if this team's roster is already full
    team_roster_size = len(draft_service.current_draft.team_rosters.get(team_name, []))
    if team_roster_size >= draft_service.current_draft.roster_size:
        return jsonify({
            'success': False,
            'message': f'{team_name} roster is full'
        }), 400
    
    # Get available players
    available = draft_service.get_available_players(all_players)
    if not available:
        return jsonify({
            'success': False,
            'message': 'No available players'
        }), 400
    
    # Get the team's current roster
    team_players = draft_service.get_team_players(all_players, team_name)
    
    # Get AI recommendation for this team
    use_ml = request.args.get('use_ml', 'true').lower() == 'true'
    recommendations = recommendation_engine.get_recommendations_for_team(
        available_players=available,
        team_players=team_players,
        draft_state=draft_service.current_draft,
        team_name=team_name,
        top_n=1,
        use_ml=use_ml
    )
    
    if not recommendations:
        return jsonify({
            'success': False,
            'message': 'No recommendations available'
        }), 400
    
    # Draft the top recommended player
    recommended_player = recommendations[0]['player']
    
    success = draft_service.draft_player(
        player_id=recommended_player.player_id,
        team_name=team_name,
        player=recommended_player
    )
    
    if success:
        draft_dict = draft_service.current_draft.to_dict()
        return jsonify({
            'success': True,
            'draft': draft_dict,
            'picked_player': recommended_player.to_dict(),
            'reasoning': recommendations[0]['reasoning'],
            'draft_complete': draft_dict.get('is_complete', False)
        })
    
    return jsonify({
        'success': False,
        'message': 'Failed to make auto-draft pick - roster may be full or draft complete'
    }), 400


@app.route('/api/ml/train', methods=['POST'])
def train_ml_models():
    """Train ML models on simulated draft data."""
    if not all_players:
        return jsonify({
            'success': False,
            'message': 'No players loaded. Load CBS and Steamer data first.'
        }), 400
    
    num_simulations = request.json.get('num_simulations', 1000) if request.json else 1000
    strategies = request.json.get('strategies', ['adp', 'category', 'random']) if request.json else ['adp', 'category', 'random']
    
    try:
        trainer = MLTrainer()
        
        # Generate training data
        training_data = trainer.generate_training_data(
            all_players=all_players,
            num_simulations=num_simulations,
            strategies=strategies
        )
        
        # Train models
        results = trainer.train_models(training_data)
        
        # Update recommendation engine
        recommendation_engine.ml_trainer = trainer
        recommendation_engine._ml_models_loaded = True
        
        return jsonify({
            'success': True,
            'message': f'Models trained on {len(training_data)} samples',
            'train_score': results['train_score'],
            'test_score': results['test_score'],
            'top_features': dict(sorted(
                results['feature_importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error training models: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)

