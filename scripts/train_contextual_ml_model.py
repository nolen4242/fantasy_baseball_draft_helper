"""
Train contextual ML model using historical draft data.

This script:
1. Loads historical drafts (2021-2025)
2. Loads historical standings
3. For each pick in each draft, calculates:
   - Player features (stats, projections, ADP, risk)
   - Contextual features (position scarcity, team needs, opponent rosters, category targeting)
   - Target variable (actual player value from final standings - normalized and balanced)
4. Trains unified ML model that handles both hitters and pitchers
5. Saves model for use in recommendations
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.historical_data_loader import HistoricalDataLoader, HistoricalPick, HistoricalStandings
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.services.ml_trainer import MLTrainer
from src.services.standings_calculator import StandingsCalculator
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService
from src.models.draft import DraftState, DraftPick
from src.models.player import Player
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from collections import defaultdict
import re
import unicodedata


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    # Remove accents/diacritics
    normalized = unicodedata.normalize('NFD', name)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    normalized = normalized.lower().strip()
    # Remove Jr., Sr., II, III, IV, etc.
    normalized = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv|v|2nd|3rd|4th)$', '', normalized)
    # Remove periods, apostrophes, hyphens
    normalized = re.sub(r"[.'\-]", "", normalized)
    normalized = normalized.replace(" ", "")
    
    return normalized


def match_historical_pick_to_player(
    historical_pick: HistoricalPick,
    all_players: List[Player],
    year: int
) -> Optional[Player]:
    """
    Match a historical pick to a Player object.
    
    Uses normalized name matching and position to find the best match.
    """
    pick_normalized = normalize_player_name(historical_pick.player_name)
    
    # First try exact normalized name match
    for player in all_players:
        if normalize_player_name(player.name) == pick_normalized:
            # Also check position matches (approximately)
            pick_pos = historical_pick.position
            player_pos = player.position
            
            # Position matching: allow some flexibility
            if historical_pick.is_pitcher:
                if player_pos in ['P', 'SP', 'RP']:
                    return player
            else:
                if player_pos not in ['P', 'SP', 'RP']:
                    # For hitters, check if position matches or is compatible
                    if pick_pos == player_pos or pick_pos in ['OF', 'MI', 'CI', 'U']:
                        return player
    
    # If no exact match, try fuzzy matching (for now, just return None)
    # Could improve with fuzzy string matching library
    return None


def calculate_contextual_features_for_historical_pick(
    historical_pick: HistoricalPick,
    picks_so_far: List[HistoricalPick],
    team_roster_before: List[HistoricalPick],
    all_teams_rosters_before: Dict[str, List[HistoricalPick]],
    all_players: List[Player],
    recommendation_engine: RecommendationEngine,
    draft_state: DraftState
) -> Dict[str, float]:
    """
    Calculate contextual features for a historical pick.
    
    Returns normalized contextual feature scores.
    """
    # Convert historical picks to Player objects for analysis
    team_players_before = []
    for pick in team_roster_before:
        player = match_historical_pick_to_player(pick, all_players, historical_pick.year)
        if player:
            team_players_before.append(player)
    
    all_rosters_before = {}
    for team_name, picks in all_teams_rosters_before.items():
        team_players = []
        for pick in picks:
            player = match_historical_pick_to_player(pick, all_players, historical_pick.year)
            if player:
                team_players.append(player)
        all_rosters_before[team_name] = team_players
    
    # Get available players (all players not yet drafted)
    drafted_player_ids = {match_historical_pick_to_player(p, all_players, historical_pick.year).player_id 
                          for p in picks_so_far 
                          if match_historical_pick_to_player(p, all_players, historical_pick.year)}
    available_players = [p for p in all_players if p.player_id not in drafted_player_ids]
    
    # Get the player for this pick
    player = match_historical_pick_to_player(historical_pick, all_players, historical_pick.year)
    if not player:
        return {
            'team_needs_score': 0.0,
            'position_scarcity_score': 0.0,
            'category_targeting_score': 0.0,
            'comparative_advantage_score': 0.0,
        }
    
    features = {}
    
    # 1. Team needs score
    try:
        needs_score, _ = recommendation_engine._analyze_team_needs(
            player, team_players_before, draft_state, available_players
        )
        features['team_needs_score'] = needs_score / 100.0  # Normalize to 0-1
    except:
        features['team_needs_score'] = 0.0
    
    # 2. Position scarcity score
    try:
        pos_score, _ = recommendation_engine._analyze_position_scarcity(
            player, team_players_before, available_players, draft_state, all_rosters_before
        )
        features['position_scarcity_score'] = pos_score / 100.0  # Normalize
    except:
        features['position_scarcity_score'] = 0.0
    
    # 3. Category targeting score
    try:
        category_priorities = recommendation_engine._optimize_category_targets(
            team_players_before, all_rosters_before, draft_state
        )
        category_score = recommendation_engine._calculate_category_target_score(
            player, team_players_before, category_priorities
        )
        features['category_targeting_score'] = category_score / 1000.0  # Normalize
    except:
        features['category_targeting_score'] = 0.0
    
    # 4. Comparative advantage score
    try:
        relative_score, _ = recommendation_engine._analyze_relative_advantage(
            player, team_players_before, all_rosters_before, draft_state, 
            available_players, historical_pick.team_name
        )
        features['comparative_advantage_score'] = relative_score / 100.0  # Normalize
    except:
        features['comparative_advantage_score'] = 0.0
    
    return features


def calculate_target_value_from_standings(
    historical_pick: HistoricalPick,
    standings: HistoricalStandings,
    all_players: List[Player],
    ml_trainer: MLTrainer
) -> float:
    """
    Calculate target value for a historical pick based on final standings.
    
    Returns normalized, balanced value score (hitters and pitchers weighted equally).
    
    Strategy:
    1. Calculate player's projected value using MLTrainer's method
    2. Use team's final total points as a multiplier to reflect actual performance
    3. Normalize to balance hitter/pitcher contributions (done in post-processing)
    """
    # Get the player
    player = match_historical_pick_to_player(historical_pick, all_players, historical_pick.year)
    if not player:
        return 0.0
    
    # Calculate base player value using MLTrainer's method
    # This gives us the player's projected statistical contribution
    base_value = ml_trainer._calculate_player_value_score(player, league_thresholds=None)
    
    # Get team's final total points (out of 130 possible: 10 categories * 13 points max)
    team_name = historical_pick.team_name
    team_total_points = standings.team_points.get(team_name, 65.0)  # Default to middle if missing
    
    # Normalize team points to a multiplier (0-1 range, centered at 0.5)
    # Team with 130 points (perfect) = 1.0, team with 65 points (average) = 0.5, team with 0 = 0.0
    # Using 65 as the baseline (middle of 0-130)
    max_possible_points = 130.0  # 10 categories * 13 points
    team_performance_multiplier = team_total_points / max_possible_points
    
    # Combine base value with team performance
    # Players on winning teams get higher target values, reflecting their actual contribution
    # We add a baseline so even bad teams' players have some value
    target_value = base_value * (0.5 + 0.5 * team_performance_multiplier)
    
    return target_value


def generate_training_data_from_historical_drafts(
    years: List[int] = None,
    all_players: List[Player] = None
) -> pd.DataFrame:
    """
    Generate training data from historical drafts with contextual features.
    
    This is the main function that orchestrates the training data generation.
    """
    if years is None:
        years = [2021, 2022, 2023, 2024, 2025]
    
    print("=" * 60)
    print("Generating Training Data from Historical Drafts")
    print("=" * 60)
    
    # Load historical data
    loader = HistoricalDataLoader()
    historical_drafts = loader.load_historical_drafts(years)
    historical_standings = loader.load_historical_standings(years)
    
    # Initialize services
    draft_service = DraftService()
    recommendation_engine = RecommendationEngine(draft_service, all_players)
    ml_trainer = MLTrainer()
    
    training_data = []
    
    for year in years:
        if year not in historical_drafts or year not in historical_standings:
            print(f"Skipping year {year} - missing data")
            continue
        
        picks = historical_drafts[year]
        standings = historical_standings[year]
        
        print(f"\nProcessing {year} draft ({len(picks)} picks)...")
        
        # Build team rosters as we go through picks
        team_rosters: Dict[str, List[HistoricalPick]] = defaultdict(list)
        picks_so_far: List[HistoricalPick] = []
        
        for pick in picks:
            # Update rosters
            team_rosters[pick.team_name].append(pick)
            picks_so_far.append(pick)
            
            # Create a draft state representing the state before this pick
            # This is needed for contextual feature calculation
            draft_state = DraftState(
                draft_id=f"historical_{year}",
                league_name="Bob Uecker League",
                total_teams=13,  # Assume 13 teams
                roster_size=21,
                my_team_name=pick.team_name
            )
            
            # Add picks before this one to draft state
            for prev_pick in picks_so_far[:-1]:  # All picks except current
                draft_pick = DraftPick(
                    pick_number=prev_pick.pick_number,
                    round=prev_pick.round,
                    team_name=prev_pick.team_name,
                    player_id=prev_pick.player_name  # Use name as ID for now
                )
                draft_state.add_pick(draft_pick)
            
            # Match pick to player
            player = match_historical_pick_to_player(pick, all_players, year)
            if not player:
                # Skip if we can't match player
                continue
            
            # Extract base player features
            base_features = ml_trainer._extract_player_features(player)
            
            # Calculate contextual features
            team_roster_before = team_rosters[pick.team_name][:-1]  # Roster before this pick
            all_rosters_before = {team: roster for team, roster in team_rosters.items() 
                                  if team != pick.team_name}
            all_rosters_before[pick.team_name] = team_roster_before
            
            contextual_features = calculate_contextual_features_for_historical_pick(
                pick, picks_so_far[:-1], team_roster_before, all_rosters_before,
                all_players, recommendation_engine, draft_state
            )
            
            # Calculate target value
            target_value = calculate_target_value_from_standings(pick, standings, all_players, ml_trainer)
            
            # Combine features
            all_features = {
                **base_features,
                **contextual_features,
                'pick_number': pick.pick_number,
                'round': pick.round,
                'pick_in_round': ((pick.pick_number - 1) % 13) + 1,
                'target_player_value': target_value
            }
            
            training_data.append(all_features)
        
        print(f"  Processed {len([d for d in training_data if d.get('round') == picks[0].round if picks])} picks from {year}")
    
    print(f"\n✅ Generated {len(training_data)} training samples from historical drafts")
    return pd.DataFrame(training_data)


if __name__ == "__main__":
    print("=" * 60)
    print("Contextual ML Model Training")
    print("=" * 60)
    
    # Load current players (for matching and feature extraction)
    print("\nStep 1: Loading players...")
    loader = MasterPlayerDictLoader()
    all_players = loader.load_all_players()
    print(f"✅ Loaded {len(all_players)} players")
    
    # Generate training data from historical drafts
    print("\nStep 2: Generating training data from historical drafts...")
    training_data = generate_training_data_from_historical_drafts(
        years=[2021, 2022, 2023, 2024, 2025],
        all_players=all_players
    )
    
    if training_data.empty:
        print("❌ No training data generated!")
        sys.exit(1)
    
    print(f"✅ Generated {len(training_data)} training samples")
    print(f"   Features: {len(training_data.columns) - 1} (excluding target)")
    
    # Normalize target variable to balance hitters and pitchers
    print("\nStep 3: Normalizing target variable for balanced hitter/pitcher training...")
    is_hitter_col = training_data.get('is_hitter', pd.Series([0.5] * len(training_data)))
    hitter_mask = (is_hitter_col > 0.5)
    pitcher_mask = ~hitter_mask
    
    hitter_targets = training_data.loc[hitter_mask, 'target_player_value']
    pitcher_targets = training_data.loc[pitcher_mask, 'target_player_value']
    
    if len(hitter_targets) > 0 and len(pitcher_targets) > 0:
        # Calculate mean and std for each group
        hitter_mean = hitter_targets.mean()
        pitcher_mean = pitcher_targets.mean()
        hitter_std = hitter_targets.std() if hitter_targets.std() > 0 else 1.0
        pitcher_std = pitcher_targets.std() if pitcher_targets.std() > 0 else 1.0
        
        # Z-score normalize each group separately (so both have mean=0, std=1)
        # This ensures hitters and pitchers are treated equally by the model
        normalized_hitter_targets = (hitter_targets - hitter_mean) / hitter_std
        normalized_pitcher_targets = (pitcher_targets - pitcher_mean) / pitcher_std
        
        # Shift both to a common mean (use 0, or could use global mean)
        # Both groups now have same distribution (mean 0, std 1)
        training_data.loc[hitter_mask, 'target_player_value'] = normalized_hitter_targets
        training_data.loc[pitcher_mask, 'target_player_value'] = normalized_pitcher_targets
        
        print(f"   Original hitter targets: mean={hitter_mean:.2f}, std={hitter_std:.2f}")
        print(f"   Original pitcher targets: mean={pitcher_mean:.2f}, std={pitcher_std:.2f}")
        print(f"   After normalization: both groups have mean≈0, std≈1")
    
    print("✅ Target variable normalized")
    
    # Train model
    print("\nStep 4: Training ML model...")
    ml_trainer = MLTrainer()
    ml_trainer.train_models(training_data)
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)

