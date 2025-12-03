"""ML model training for draft recommendations."""
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from src.models.player import Player
from src.services.draft_simulator import DraftSimulator
from src.services.standings_calculator import StandingsCalculator


class MLTrainer:
    """Trains ML models on simulated draft data."""
    
    def __init__(self, models_dir: str = None):
        if models_dir is None:
            project_root = Path(__file__).parent.parent.parent
            models_dir = project_root / "ml" / "models"
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.value_model = None
        self.scaler = StandardScaler()
    
    def generate_training_data(
        self,
        all_players: List[Player],
        num_simulations: int = 1000,
        strategies: List[str] = None
    ) -> pd.DataFrame:
        """
        Generate training data by simulating drafts.
        
        Args:
            all_players: All available players
            num_simulations: Number of drafts to simulate
            strategies: List of strategies to use (e.g., ['adp', 'category', 'random'])
        
        Returns:
            DataFrame with features and target (final rank)
        """
        if strategies is None:
            strategies = ['adp', 'category', 'random']
        
        simulator = DraftSimulator(all_players)
        calculator = StandingsCalculator()
        
        training_data = []
        
        print(f"Generating {num_simulations} simulated drafts...")
        
        for sim_num in range(num_simulations):
            if (sim_num + 1) % 100 == 0:
                print(f"  Completed {sim_num + 1}/{num_simulations} simulations...")
            
            # Pick a random strategy
            strategy = np.random.choice(strategies)
            
            # Simulate draft
            draft_result = simulator.simulate_draft(strategy=strategy)
            team_rosters = draft_result['team_rosters']
            pick_history = draft_result['pick_history']
            
            # Calculate standings
            standings = calculator.calculate_standings(team_rosters)
            
            # Extract features for each pick
            for pick in pick_history:
                team_name = pick['team_name']
                player_id = pick['player_id']
                
                # Find the player
                player = next((p for p in all_players if p.player_id == player_id), None)
                if not player:
                    continue
                
                # Get team state at time of pick
                pick_number = pick['pick_number']
                round_num = pick['round']
                
                # Get roster before this pick
                roster_before = [
                    p for p in pick_history
                    if p['team_name'] == team_name and p['pick_number'] < pick_number
                ]
                roster_players = [
                    next((p for p in all_players if p.player_id == r['player_id']), None)
                    for r in roster_before
                ]
                roster_players = [p for p in roster_players if p is not None]
                
                # Calculate features
                features = self._extract_features(
                    player, roster_players, all_players, pick_number, round_num, team_rosters
                )
                
                # Get target (final rank of the team)
                final_rank = standings['final_rankings'].index(team_name) + 1
                
                training_data.append({
                    **features,
                    'target_final_rank': final_rank
                })
        
        print(f"Generated {len(training_data)} training samples")
        return pd.DataFrame(training_data)
    
    def _extract_features(
        self,
        player: Player,
        roster_before: List[Player],
        all_players: List[Player],
        pick_number: int,
        round_num: int,
        all_rosters: Dict[str, List[Player]]
    ) -> Dict:
        """Extract features for a player pick."""
        # Player stats
        features = {
            'player_adp': player.adp or 999,
            'player_hr': player.projected_home_runs or 0,
            'player_obp': player.projected_obp or 0,
            'player_r': player.projected_runs or 0,
            'player_rbi': player.projected_rbi or 0,
            'player_sb': player.projected_stolen_bases or 0,
            'player_w': player.projected_wins or 0,
            'player_qs': player.projected_quality_starts or 0,
            'player_k': player.projected_strikeouts or 0,
            'player_sv': player.projected_saves or 0,
            'player_hd': player.projected_holds or 0,
            'player_era': player.projected_era or 5.0,
            'player_whip': player.projected_whip or 1.5,
            'is_hitter': 1 if player.position not in ['SP', 'RP', 'P'] else 0,
            'is_pitcher': 1 if player.position in ['SP', 'RP', 'P'] else 0,
        }
        
        # Draft context
        features['pick_number'] = pick_number
        features['round'] = round_num
        features['picks_remaining'] = (13 * 21) - pick_number
        
        # Team state
        features['roster_size'] = len(roster_before)
        features['hitters_on_roster'] = sum(1 for p in roster_before if p.position not in ['SP', 'RP', 'P'])
        features['pitchers_on_roster'] = sum(1 for p in roster_before if p.position in ['SP', 'RP', 'P'])
        
        # Position need
        position_counts = {}
        for pos in ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP', 'P']:
            position_counts[pos] = sum(1 for p in roster_before if p.position == pos)
        
        features['needs_' + player.position.lower()] = 1 if position_counts.get(player.position, 0) == 0 else 0
        
        # Category totals before pick
        calculator = StandingsCalculator()
        totals_before = calculator._calculate_team_totals(roster_before)
        features['current_hr'] = totals_before['HR']
        features['current_obp'] = totals_before['OBP']
        features['current_r'] = totals_before['R']
        features['current_rbi'] = totals_before['RBI']
        features['current_sb'] = totals_before['SB']
        features['current_w'] = totals_before['W']
        features['current_qs'] = totals_before['QS']
        features['current_k'] = totals_before['K']
        features['current_sv'] = totals_before['SV']
        features['current_hd'] = totals_before['HD']
        features['current_era'] = totals_before['ERA']
        features['current_whip'] = totals_before['WHIP']
        
        # Positional scarcity
        available_at_position = sum(1 for p in all_players if p.position == player.position)
        features['position_scarcity'] = available_at_position / len(all_players) if all_players else 0
        
        return features
    
    def train_models(self, training_data: pd.DataFrame):
        """Train ML models on training data."""
        # Separate features and target
        feature_cols = [col for col in training_data.columns if col != 'target_final_rank']
        X = training_data[feature_cols].values
        y = training_data['target_final_rank'].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )
        
        # Train Random Forest
        print("Training Random Forest model...")
        self.value_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=20,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.value_model.fit(X_train, y_train)
        
        # Evaluate
        train_score = self.value_model.score(X_train, y_train)
        test_score = self.value_model.score(X_test, y_test)
        
        print(f"Random Forest - Train R²: {train_score:.4f}, Test R²: {test_score:.4f}")
        
        # Save models
        self._save_models()
        
        return {
            'train_score': train_score,
            'test_score': test_score,
            'feature_importance': dict(zip(feature_cols, self.value_model.feature_importances_))
        }
    
    def _save_models(self):
        """Save trained models to disk."""
        model_file = self.models_dir / "value_model.pkl"
        scaler_file = self.models_dir / "scaler.pkl"
        
        with open(model_file, 'wb') as f:
            pickle.dump(self.value_model, f)
        
        with open(scaler_file, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        print(f"Models saved to {self.models_dir}")
    
    def load_models(self) -> bool:
        """Load trained models from disk."""
        model_file = self.models_dir / "value_model.pkl"
        scaler_file = self.models_dir / "scaler.pkl"
        
        if not model_file.exists() or not scaler_file.exists():
            return False
        
        with open(model_file, 'rb') as f:
            self.value_model = pickle.load(f)
        
        with open(scaler_file, 'rb') as f:
            self.scaler = pickle.load(f)
        
        return True
    
    def predict_player_value(
        self,
        player: Player,
        roster_before: List[Player],
        all_players: List[Player],
        pick_number: int,
        round_num: int,
        all_rosters: Dict[str, List[Player]]
    ) -> float:
        """Predict how much a player will improve final rank."""
        if self.value_model is None:
            if not self.load_models():
                return 0.0
        
        # Extract features
        features = self._extract_features(
            player, roster_before, all_players, pick_number, round_num, all_rosters
        )
        
        # Convert to array and scale
        feature_cols = list(features.keys())
        X = np.array([[features[col] for col in feature_cols]])
        X_scaled = self.scaler.transform(X)
        
        # Predict (lower rank = better, so we negate)
        predicted_rank = self.value_model.predict(X_scaled)[0]
        
        # Return value (negative because lower rank is better)
        return -predicted_rank

