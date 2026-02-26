"""Flask API for the draft helper application."""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import sys
import random
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


def _build_team_rosters_players() -> dict:
    """Build {team_name: [Player]} from current draft, deduplicating by player_id."""
    result = {}
    for team_name, player_ids in draft_service.current_draft.team_rosters.items():
        seen = set()
        players = []
        for pid in player_ids:
            if pid not in seen:
                seen.add(pid)
                player = next((p for p in all_players if p.player_id == pid), None)
                if player:
                    players.append(player)
        result[team_name] = players
    return result

# Draft strategy setting
draft_strategy = 'balanced'


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
    """Make a draft pick. Auto-creates a draft if one doesn't exist."""
    data = request.json
    player_id = data['player_id']
    requested_team_name = data.get('team_name')  # Team name from request (for manual picks)
    
    # Auto-create a draft if one doesn't exist
    if not draft_service.current_draft:
        # Create a default draft
        import time
        default_team_name = requested_team_name if requested_team_name else 'Runtime Terror'
        draft = draft_service.create_draft(
            draft_id=f"draft_{int(time.time())}",
            league_name='Bob Uecker League',
            total_teams=13,
            roster_size=21,
            my_team_name=default_team_name
        )
    
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
    
    # Check if there's an available slot for this player's eligible positions
    from src.services.team_service import TeamService
    team_service = TeamService()
    
    if not team_service.has_available_slot_for_player(team_name, player):
        eligible_positions = team_service._determine_eligible_positions(player)
        eligible_str = ', '.join(eligible_positions)
        return jsonify({
            'success': False,
            'message': f'Cannot draft {player.name} - all eligible position slots are filled ({eligible_str})'
        }), 400
    
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
    """Completely restart the draft - clears all picks and resets all team rosters.
    Works regardless of whether there's an active draft or not."""
    from src.services.cleanup_service import CleanupService
    from src.services.draft_order import DraftOrder
    
    # Clean up all team rosters (always do this, even if no active draft)
    cleanup = CleanupService()
    cleanup.cleanup_all_team_rosters()
    
    # If there's an active draft, restart it with the same settings
    if draft_service.current_draft:
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
            'message': 'Draft restarted - all picks and rosters cleared'
        })
    else:
        # No active draft, but we still cleared all rosters
        return jsonify({
            'success': True,
            'draft': None,
            'message': 'All team rosters cleared (no active draft to restart)'
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
    
    # Get current pick number
    current_pick = len(draft_service.current_draft.picks) + 1
    
    # Filter available players to those within 15 picks of ADP or current pick
    adp_range_players = []
    for player in available:
        if player.adp is not None:
            # Player has ADP - check if within 15 picks
            if abs(player.adp - current_pick) <= 15:
                adp_range_players.append(player)
        else:
            # No ADP - include if we're in later rounds (pick > 200) or if it's a reasonable late pick
            if current_pick > 200:
                adp_range_players.append(player)
    
    # If no players in ADP range, use all available players
    if not adp_range_players:
        adp_range_players = available
    
    # Get AI recommendations for this team (get top 10 to have a good pool)
    use_ml = request.args.get('use_ml', 'true').lower() == 'true'
    recommendations = recommendation_engine.get_recommendations_for_team(
        available_players=available,
        team_players=team_players,
        draft_state=draft_service.current_draft,
        team_name=team_name,
        top_n=10,
        use_ml=use_ml
    )
    
    # Create a weighted pool of ADP-appropriate players
    # AI recommended players get moderate weight boost (2x), others get 1x
    weighted_pool = []
    
    ai_recommended_ids = {rec['player'].player_id for rec in recommendations}
    for player in adp_range_players:
        from src.services.team_service import TeamService
        team_service = TeamService()
        if not team_service.has_available_slot_for_player(team_name, player):
            continue
        
        if player.player_id in ai_recommended_ids:
            weighted_pool.extend([player] * 2)
        else:
            weighted_pool.append(player)
    
    if not weighted_pool:
        return jsonify({
            'success': False,
            'message': 'No suitable players available within ADP range'
        }), 400
    
    # Randomly select from weighted pool
    selected_player = random.choice(weighted_pool)
    
    # Find which recommendation this was (if any)
    recommended_player = selected_player
    reasoning = "Random selection from ADP range"
    for rec in recommendations:
        if rec['player'].player_id == selected_player.player_id:
            reasoning = rec['reasoning']
            break
    
    success = draft_service.draft_player(
        player_id=selected_player.player_id,
        team_name=team_name,
        player=selected_player
    )
    
    if success:
        draft_dict = draft_service.current_draft.to_dict()
        return jsonify({
            'success': True,
            'draft': draft_dict,
            'picked_player': selected_player.to_dict(),
            'reasoning': reasoning,
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


@app.route('/api/standings', methods=['GET'])
def get_standings():
    """Get current roto standings/leaderboard based on projected stats."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400

    from src.services.standings_calculator import StandingsCalculator
    calc = StandingsCalculator()

    team_rosters_players = _build_team_rosters_players()

    standings = calc.calculate_standings(team_rosters_players)

    serializable_totals = {}
    for team_name, totals in standings['category_totals'].items():
        serializable_totals[team_name] = {k: round(float(v), 3) for k, v in totals.items()}

    serializable_cat_points = {}
    for cat, pts in standings['category_points'].items():
        serializable_cat_points[cat] = {t: round(float(v), 1) for t, v in pts.items()}

    return jsonify({
        'success': True,
        'category_totals': serializable_totals,
        'category_points': serializable_cat_points,
        'category_rankings': standings['category_rankings'],
        'batting_points': {t: round(float(v), 1) for t, v in standings['batting_points'].items()},
        'pitching_points': {t: round(float(v), 1) for t, v in standings['pitching_points'].items()},
        'total_points': {t: round(float(v), 1) for t, v in standings['total_points'].items()},
        'final_rankings': standings['final_rankings']
    })


@app.route('/api/player/<player_id>/analysis', methods=['GET'])
def get_player_analysis(player_id):
    """Get draft analysis (pros/cons/reasoning) for a specific player."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    player = next((p for p in all_players if p.player_id == player_id), None)
    if not player:
        return jsonify({'success': False, 'message': 'Player not found'}), 404

    recommendation_engine.all_players = all_players
    available = draft_service.get_available_players(all_players)
    my_team = draft_service.get_my_team_players(all_players)

    recs = recommendation_engine.get_recommendations(
        available_players=available,
        my_team=my_team,
        draft_state=draft_service.current_draft,
        top_n=200,
        use_ml=False,
    )

    rec = next((r for r in recs if r['player'].player_id == player_id), None)

    current_pick = len(draft_service.current_draft.picks) + 1
    adp = player.adp
    is_hitter = player.position not in ('SP', 'RP', 'P')

    pros = []
    cons = []

    if rec:
        score = rec['score']
        reasoning = rec['reasoning']
        rank_in_recs = next((i + 1 for i, r in enumerate(recs) if r['player'].player_id == player_id), None)
        if rank_in_recs and rank_in_recs <= 3:
            pros.append(f'Ranked #{rank_in_recs} recommendation right now')
        elif rank_in_recs and rank_in_recs <= 10:
            pros.append(f'Top 10 recommendation (#{rank_in_recs})')
        elif rank_in_recs:
            cons.append(f'Ranked #{rank_in_recs} of {len(recs)} available — better options exist')
    else:
        score = 0
        reasoning = 'Not in current recommendation pool'
        cons.append('Not currently recommended')

    if adp:
        adp_diff = adp - current_pick
        if adp_diff > 15:
            cons.append(f'Major reach: ADP {adp:.1f} is {adp_diff:.0f} picks away — will likely still be available later')
        elif adp_diff > 5:
            cons.append(f'Slight reach: ADP {adp:.1f} is {adp_diff:.0f} picks ahead of current pick {current_pick}')
        elif adp_diff < -10:
            pros.append(f'Great value: ADP {adp:.1f} — should have gone {-adp_diff:.0f} picks ago')
        elif adp_diff < -3:
            pros.append(f'Good value: ADP {adp:.1f} at pick {current_pick}')
        else:
            pros.append(f'Right on ADP value ({adp:.1f} at pick {current_pick})')

    from src.services.team_service import TeamService
    ts = TeamService()
    eligible = ts._determine_eligible_positions(player)
    has_slot = ts.has_available_slot_for_player(draft_service.current_draft.my_team_name, player)
    if has_slot:
        pros.append(f'Fills an open roster slot ({", ".join(eligible[:3])})')
    else:
        cons.append('No open roster slot for this player')

    hitter_count = sum(1 for p in my_team if p.position not in ('SP', 'RP', 'P'))
    pitcher_count = len(my_team) - hitter_count
    if is_hitter and hitter_count >= 11:
        cons.append(f'Already have {hitter_count} hitters (need 11)')
    if not is_hitter and pitcher_count >= 9:
        cons.append(f'Already have {pitcher_count} pitchers (need 9)')

    if is_hitter:
        cats = {'HR': player.projected_home_runs, 'SB': player.projected_stolen_bases,
                'OBP': player.projected_obp, 'R': player.projected_runs, 'RBI': player.projected_rbi}
        strong = [c for c, v in cats.items() if v and v > 0]
        if player.projected_home_runs and player.projected_home_runs >= 30:
            pros.append(f'Elite power ({int(player.projected_home_runs)} HR)')
        if player.projected_stolen_bases and player.projected_stolen_bases >= 20:
            pros.append(f'Speed threat ({int(player.projected_stolen_bases)} SB)')
        if player.projected_obp and player.projected_obp >= 0.370:
            pros.append(f'Elite OBP ({player.projected_obp:.3f})')
        if player.projected_obp and player.projected_obp < 0.300:
            cons.append(f'Low OBP ({player.projected_obp:.3f})')
    else:
        if player.projected_era and player.projected_era <= 3.00:
            pros.append(f'Ace-level ERA ({player.projected_era:.2f})')
        if player.projected_era and player.projected_era >= 4.00:
            cons.append(f'High ERA ({player.projected_era:.2f})')
        if player.projected_strikeouts and player.projected_strikeouts >= 200:
            pros.append(f'Elite strikeout arm ({int(player.projected_strikeouts)} K)')
        if player.projected_saves and player.projected_saves >= 25:
            pros.append(f'Closer with {int(player.projected_saves)} projected saves')
        if player.projected_whip and player.projected_whip <= 1.10:
            pros.append(f'Elite WHIP ({player.projected_whip:.2f})')
        if player.projected_whip and player.projected_whip >= 1.30:
            cons.append(f'High WHIP ({player.projected_whip:.2f})')

    return jsonify({
        'success': True,
        'player_id': player_id,
        'score': round(score, 1),
        'reasoning': reasoning,
        'pros': pros,
        'cons': cons,
    })


@app.route('/api/draft/board', methods=['GET'])
def get_draft_board():
    """Get draft board — every pick organized by round and pick-in-round."""
    if not draft_service.current_draft:
        return jsonify({
            'success': False,
            'message': 'No active draft'
        }), 400

    draft = draft_service.current_draft
    board = []
    for pick in draft.picks:
        player = next((p for p in all_players if p.player_id == pick.player_id), None)
        board.append({
            'pick_number': pick.pick_number,
            'round': pick.round,
            'team_name': pick.team_name,
            'player_id': pick.player_id,
            'player_name': player.name if player else pick.player_id,
            'position': player.position if player else '',
        })

    return jsonify({
        'success': True,
        'board': board,
        'total_teams': draft.total_teams,
        'roster_size': draft.roster_size,
        'picks_made': len(draft.picks),
        'total_picks': draft.total_teams * draft.roster_size,
    })


@app.route('/api/player/<player_id>/eligible-positions', methods=['GET'])
def get_eligible_positions(player_id):
    player = next((p for p in all_players if p.player_id == player_id), None)
    if not player:
        return jsonify({'success': False, 'message': 'Player not found'}), 404
    from src.services.team_service import TeamService
    ts = TeamService()
    positions = ts._determine_eligible_positions(player)
    return jsonify({'success': True, 'player_id': player_id, 'eligible_positions': positions})


@app.route('/api/team/category-needs', methods=['GET'])
def get_category_needs():
    """Return how the user's team ranks in each category relative to all teams."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    from src.services.standings_calculator import StandingsCalculator
    calc = StandingsCalculator()

    team_rosters_players = _build_team_rosters_players()

    standings = calc.calculate_standings(team_rosters_players)

    my_team = draft_service.current_draft.my_team_name
    all_categories = calc.BATTING_CATEGORIES + calc.PITCHING_CATEGORIES
    category_details = {}

    for cat in all_categories:
        my_value = standings['category_totals'].get(my_team, {}).get(cat, 0.0)
        rankings_list = standings['category_rankings'].get(cat, [])
        try:
            rank = rankings_list.index(my_team) + 1
        except ValueError:
            rank = len(rankings_list) + 1

        if rank >= 10:
            need = 'critical'
        elif rank >= 7:
            need = 'moderate'
        elif rank >= 4:
            need = 'good'
        else:
            need = 'strong'

        category_details[cat] = {
            'value': round(float(my_value), 3),
            'rank': rank,
            'need': need,
        }

    sorted_needs = sorted(category_details.keys(), key=lambda c: -category_details[c]['rank'])

    return jsonify({
        'success': True,
        'team_name': my_team,
        'categories': category_details,
        'needs_sorted': sorted_needs,
    })


@app.route('/api/draft/batch-revert', methods=['POST'])
def batch_revert():
    """Revert all picks from the most recent back to pick N (inclusive)."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    data = request.json or {}
    revert_to = data.get('revert_to_pick')
    if revert_to is None:
        return jsonify({'success': False, 'message': 'revert_to_pick is required'}), 400

    revert_to = int(revert_to)
    picks = draft_service.current_draft.picks
    if not picks:
        return jsonify({'success': False, 'message': 'No picks to revert'}), 400

    last_pick = picks[-1].pick_number
    if revert_to < 1 or revert_to > last_pick:
        return jsonify({
            'success': False,
            'message': f'revert_to_pick must be between 1 and {last_pick}'
        }), 400

    reverted = []
    for pick_num in range(last_pick, revert_to - 1, -1):
        ok = draft_service.revert_pick(pick_num)
        if ok:
            reverted.append(pick_num)

    return jsonify({
        'success': True,
        'reverted_picks': reverted,
        'draft': draft_service.current_draft.to_dict(),
    })


@app.route('/api/draft/strategy', methods=['GET'])
def get_draft_strategy():
    """Return the current draft strategy."""
    return jsonify({'success': True, 'strategy': draft_strategy})


@app.route('/api/draft/strategy', methods=['POST'])
def set_draft_strategy():
    """Set the draft strategy."""
    global draft_strategy
    data = request.json or {}
    strategy = data.get('strategy')
    valid = {'balanced', 'stars_and_scrubs', 'pitching_heavy', 'hitting_heavy'}
    if strategy not in valid:
        return jsonify({
            'success': False,
            'message': f'Invalid strategy. Must be one of: {", ".join(sorted(valid))}'
        }), 400
    draft_strategy = strategy
    return jsonify({'success': True, 'strategy': draft_strategy})


@app.route('/api/trade/analyze', methods=['POST'])
def analyze_trade():
    """Analyze a hypothetical trade between two teams."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    data = request.json or {}
    team_a_name = data.get('team_a')
    team_b_name = data.get('team_b')
    players_from_a = data.get('players_from_a', [])
    players_from_b = data.get('players_from_b', [])

    if not team_a_name or not team_b_name:
        return jsonify({'success': False, 'message': 'team_a and team_b are required'}), 400

    from src.services.standings_calculator import StandingsCalculator
    calc = StandingsCalculator()

    team_rosters_players = _build_team_rosters_players()

    before = calc.calculate_standings(team_rosters_players)

    before_a_rank = before['final_rankings'].index(team_a_name) + 1 if team_a_name in before['final_rankings'] else None
    before_b_rank = before['final_rankings'].index(team_b_name) + 1 if team_b_name in before['final_rankings'] else None
    before_a_pts = round(float(before['total_points'].get(team_a_name, 0)), 1)
    before_b_pts = round(float(before['total_points'].get(team_b_name, 0)), 1)

    a_player_objs = [p for p in all_players if p.player_id in players_from_a]
    b_player_objs = [p for p in all_players if p.player_id in players_from_b]

    after_rosters = {}
    for tn, roster in team_rosters_players.items():
        after_rosters[tn] = list(roster)

    after_rosters[team_a_name] = [p for p in after_rosters.get(team_a_name, []) if p.player_id not in players_from_a] + b_player_objs
    after_rosters[team_b_name] = [p for p in after_rosters.get(team_b_name, []) if p.player_id not in players_from_b] + a_player_objs

    after = calc.calculate_standings(after_rosters)

    after_a_rank = after['final_rankings'].index(team_a_name) + 1 if team_a_name in after['final_rankings'] else None
    after_b_rank = after['final_rankings'].index(team_b_name) + 1 if team_b_name in after['final_rankings'] else None
    after_a_pts = round(float(after['total_points'].get(team_a_name, 0)), 1)
    after_b_pts = round(float(after['total_points'].get(team_b_name, 0)), 1)

    all_categories = calc.BATTING_CATEGORIES + calc.PITCHING_CATEGORIES
    category_impact = {}
    for cat in all_categories:
        category_impact[cat] = {
            'team_a_before': round(float(before['category_totals'].get(team_a_name, {}).get(cat, 0)), 3),
            'team_a_after': round(float(after['category_totals'].get(team_a_name, {}).get(cat, 0)), 3),
            'team_b_before': round(float(before['category_totals'].get(team_b_name, {}).get(cat, 0)), 3),
            'team_b_after': round(float(after['category_totals'].get(team_b_name, {}).get(cat, 0)), 3),
        }

    return jsonify({
        'success': True,
        'before_standings': {
            'team_a_rank': before_a_rank,
            'team_a_points': before_a_pts,
            'team_b_rank': before_b_rank,
            'team_b_points': before_b_pts,
        },
        'after_standings': {
            'team_a_rank': after_a_rank,
            'team_a_points': after_a_pts,
            'team_b_rank': after_b_rank,
            'team_b_points': after_b_pts,
        },
        'category_impact': category_impact,
    })


@app.route('/api/draft/win-probability', methods=['GET'])
def get_win_probability():
    """Run a Monte Carlo simulation to estimate each team's win probability."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    iterations = min(int(request.args.get('iterations', 100)), 500)
    draft = draft_service.current_draft

    from src.services.standings_calculator import StandingsCalculator
    import copy

    calc = StandingsCalculator()
    total_picks = draft.total_teams * draft.roster_size
    current_picks_count = len(draft.picks)

    if current_picks_count >= total_picks:
        team_rosters_players = _build_team_rosters_players()
        standings = calc.calculate_standings(team_rosters_players)
        winner = standings['final_rankings'][0] if standings['final_rankings'] else None
        probs = {tn: 0.0 for tn in draft.team_rosters}
        if winner:
            probs[winner] = 1.0
        return jsonify({
            'success': True,
            'win_probability': probs,
            'my_team_probability': probs.get(draft.my_team_name, 0.0),
            'iterations': 1,
        })

    available = draft_service.get_available_players(all_players)
    available_sorted = sorted(available, key=lambda p: (p.adp is None, p.adp or float('inf')))

    win_counts = {tn: 0 for tn in draft.team_rosters}

    for _ in range(iterations):
        sim_rosters = {tn: list(pids) for tn, pids in draft.team_rosters.items()}
        sim_available_ids = {p.player_id for p in available_sorted}
        sim_pool = list(available_sorted)

        for pick_idx in range(current_picks_count + 1, total_picks + 1):
            team_for_pick = DraftOrder.get_team_for_pick(pick_idx, draft.total_teams)
            if len(sim_rosters.get(team_for_pick, [])) >= draft.roster_size:
                continue
            if not sim_pool:
                break

            if team_for_pick == draft.my_team_name:
                chosen = sim_pool[0]
            else:
                candidates = [p for p in sim_pool if p.adp is not None and abs(p.adp - pick_idx) <= 15]
                if not candidates:
                    candidates = sim_pool[:20] if len(sim_pool) >= 20 else sim_pool
                chosen = random.choice(candidates)

            sim_rosters[team_for_pick].append(chosen.player_id)
            sim_pool.remove(chosen)

        team_rosters_players = {}
        player_map = {p.player_id: p for p in all_players}
        for tn, pids in sim_rosters.items():
            seen_sim = set()
            deduped = []
            for pid in pids:
                if pid not in seen_sim and pid in player_map:
                    seen_sim.add(pid)
                    deduped.append(player_map[pid])
            team_rosters_players[tn] = deduped

        standings = calc.calculate_standings(team_rosters_players)
        if standings['final_rankings']:
            winner = standings['final_rankings'][0]
            if winner in win_counts:
                win_counts[winner] += 1

    probs = {tn: round(count / iterations, 4) for tn, count in win_counts.items()}

    return jsonify({
        'success': True,
        'win_probability': probs,
        'my_team_probability': probs.get(draft.my_team_name, 0.0),
        'iterations': iterations,
    })


@app.route('/api/draft/recap', methods=['GET'])
def get_draft_recap():
    """Return a draft summary with picks by team, grades, and notable picks."""
    if not draft_service.current_draft:
        return jsonify({'success': False, 'message': 'No active draft'}), 400

    from src.services.standings_calculator import StandingsCalculator
    calc = StandingsCalculator()
    draft = draft_service.current_draft

    team_rosters_players = _build_team_rosters_players()

    standings = calc.calculate_standings(team_rosters_players)

    teams_recap = {}
    for tn, pids in draft.team_rosters.items():
        team_picks = [pk for pk in draft.picks if pk.team_name == tn]
        players = team_rosters_players.get(tn, [])

        best_pick = None
        best_value = float('-inf')
        biggest_reach = None
        biggest_reach_value = float('-inf')

        for pk in team_picks:
            player = next((p for p in all_players if p.player_id == pk.player_id), None)
            if player and player.adp is not None:
                value_diff = player.adp - pk.pick_number
                if value_diff > best_value:
                    best_value = value_diff
                    best_pick = {
                        'player_name': player.name,
                        'player_id': player.player_id,
                        'pick_number': pk.pick_number,
                        'adp': player.adp,
                        'value': round(value_diff, 1),
                    }
                reach_diff = pk.pick_number - player.adp
                if reach_diff > biggest_reach_value:
                    biggest_reach_value = reach_diff
                    biggest_reach = {
                        'player_name': player.name,
                        'player_id': player.player_id,
                        'pick_number': pk.pick_number,
                        'adp': player.adp,
                        'reach': round(reach_diff, 1),
                    }

        teams_recap[tn] = {
            'player_count': len(pids),
            'batting_points': round(float(standings['batting_points'].get(tn, 0)), 1),
            'pitching_points': round(float(standings['pitching_points'].get(tn, 0)), 1),
            'total_points': round(float(standings['total_points'].get(tn, 0)), 1),
            'best_pick': best_pick,
            'biggest_reach': biggest_reach,
            'picks': [
                {
                    'pick_number': pk.pick_number,
                    'round': pk.round,
                    'player_id': pk.player_id,
                    'player_name': next((p.name for p in all_players if p.player_id == pk.player_id), pk.player_id),
                }
                for pk in team_picks
            ],
        }

    point_values = [info['total_points'] for info in teams_recap.values()]
    avg_points = sum(point_values) / len(point_values) if point_values else 0

    grades = {}
    for tn, info in teams_recap.items():
        diff = info['total_points'] - avg_points
        if diff >= avg_points * 0.15:
            grade = 'A'
        elif diff >= avg_points * 0.05:
            grade = 'B'
        elif diff >= -avg_points * 0.05:
            grade = 'C'
        elif diff >= -avg_points * 0.15:
            grade = 'D'
        else:
            grade = 'F'
        grades[tn] = grade

    return jsonify({
        'success': True,
        'teams': teams_recap,
        'grades': grades,
        'average_points': round(avg_points, 1),
    })


if __name__ == '__main__':
    app.run(debug=True, port=5001)

