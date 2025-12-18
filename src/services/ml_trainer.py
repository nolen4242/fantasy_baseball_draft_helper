"""ML model training for draft recommendations using player data features only."""
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from src.models.player import Player
from src.services.standings_calculator import StandingsCalculator


class MLTrainer:
    """
    Trains ML models on player data features only.
    NO DRAFT DATA (historical or simulated) is used.
    Model learns to predict player value based on statistical features.
    """
    
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
        league_thresholds: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Generate training data from player features only.
        NO DRAFT DATA (historical or simulated) is used.
        
        The model learns to predict player value based on:
        - Statistical features (projections, advanced metrics, Statcast)
        - Risk factors (injury, age, sample size)
        - Context (ADP, park factors, news sentiment)
        
        Target variable: Composite player value score based on league categories.
        
        Args:
            all_players: All available players (with merged data from all sources)
            league_thresholds: Stats needed to win each category (for value calculation)
        
        Returns:
            DataFrame with features and target (player value score)
        """
        calculator = StandingsCalculator()
        training_data = []
        
        print(f"Generating training data from {len(all_players)} players...")
        print("Using player data features only - NO DRAFT DATA")
        
        # Calculate player value scores based on league categories
        for player in all_players:
            if not player:
                continue
            
            # Extract player features
            features = self._extract_player_features(player)
            
            # Calculate target: composite player value score
            # Based on how much this player contributes to league-winning categories
            value_score = self._calculate_player_value_score(player, league_thresholds)
            
            training_data.append({
                **features,
                'target_player_value': value_score
            })
        
        print(f"Generated {len(training_data)} training samples from player data")
        return pd.DataFrame(training_data)
    
    def _extract_player_features(self, player: Player) -> Dict[str, float]:
        """Extract features from player data only (no draft context)."""
        is_pitcher = player.position in ['SP', 'RP', 'P']
        is_hitter = not is_pitcher
        
        features = {}
        
        # === Statistical Features ===
        if is_hitter:
            features['hr'] = player.projected_home_runs or 0
            features['r'] = player.projected_runs or 0
            features['rbi'] = player.projected_rbi or 0
            features['sb'] = player.projected_stolen_bases or 0
            features['obp'] = player.projected_obp or 0.3
        else:
            features['w'] = player.projected_wins or 0
            features['k'] = player.projected_strikeouts or 0
            features['era'] = player.projected_era or 5.0
            features['whip'] = player.projected_whip or 1.5
            features['sv'] = player.projected_saves or 0
            features['hd'] = player.projected_holds or 0
            features['qs'] = player.projected_quality_starts or 0
        
        # === Advanced Metrics ===
        if is_hitter:
            features['wrc_plus'] = player.br_wrc_plus or 100
            features['ops_plus'] = player.br_ops_plus or 100
            features['war'] = player.br_war or 0
        else:
            features['era_plus'] = player.br_era_plus or 100
            features['fip'] = player.br_fip or 4.0
            features['xfip'] = player.br_xfip or 4.0
            features['war'] = player.br_war or 0
        
        # === Statcast Features ===
        if is_hitter:
            features['exit_velocity'] = player.savant_exit_velocity or 0
            features['barrel_rate'] = player.savant_barrel_rate or 0
            features['hard_hit_rate'] = player.savant_hard_hit_rate or 0
            features['xba'] = player.savant_xba or 0
            features['xwoba'] = player.savant_xwoba or 0
            features['sprint_speed'] = player.savant_sprint_speed or 0
        else:
            features['spin_rate'] = player.savant_spin_rate or 0
            features['velocity'] = player.savant_velocity or 0
        
        # === Projection System Features (Multiple Systems) ===
        if is_hitter:
            # Average across projection systems
            proj_hr = [p for p in [
                player.projected_home_runs, player.br_proj_hr,
                player.fg_steamer_hr, player.fg_zips_hr, player.fg_thebat_hr, player.fg_atc_hr
            ] if p is not None]
            features['avg_proj_hr'] = np.mean(proj_hr) if proj_hr else 0
            features['proj_std_hr'] = np.std(proj_hr) if len(proj_hr) > 1 else 0
        else:
            proj_era = [p for p in [
                player.projected_era, player.br_proj_era,
                player.fg_steamer_era, player.fg_zips_era, player.fg_atc_era
            ] if p is not None]
            features['avg_proj_era'] = np.mean(proj_era) if proj_era else 5.0
            features['proj_std_era'] = np.std(proj_era) if len(proj_era) > 1 else 0
        
        # === Risk Features ===
        features['injury_risk'] = player.injury_risk_score or 0.0
        features['sample_size_confidence'] = player.sample_size_confidence or 0.5
        features['age_decline'] = player.age_decline_factor or 1.0
        features['age'] = player.age or 27
        features['news_sentiment'] = player.news_sentiment or 0.0
        features['contract_year'] = 1.0 if player.contract_year else 0.0
        features['current_injury'] = 1.0 if player.current_injury else 0.0
        
        # === Context Features ===
        features['adp'] = player.nfbc_adp or player.adp or 999
        features['park_factor_offense'] = player.park_factor_offense or 1.0
        features['park_factor_hr'] = player.park_factor_hr or 1.0
        features['bb_forecaster'] = player.bb_forecaster_prediction or 0.0
        
        # === Position ===
        features['is_hitter'] = 1.0 if is_hitter else 0.0
        features['is_pitcher'] = 1.0 if is_pitcher else 0.0
        
        return features
    
    def _calculate_player_value_score(
        self,
        player: Player,
        league_thresholds: Optional[Dict[str, float]]
    ) -> float:
        """
        Calculate composite player value score based on league categories.
        Higher score = more valuable player.
        """
        is_pitcher = player.position in ['SP', 'RP', 'P']
        value = 0.0
        
        if is_pitcher:
            # Pitching categories: W, K, ERA, WHIP, SV, HD
            # Positive categories (higher is better)
            value += (player.projected_wins or 0) * 2.0
            value += (player.projected_strikeouts or 0) * 0.25
            value += (player.projected_saves or 0) * 3.0
            value += (player.projected_holds or 0) * 1.5
            value += (player.projected_quality_starts or 0) * 2.0
            
            # Negative categories (lower is better) - invert
            if player.projected_era:
                value += max(0, (5.0 - player.projected_era) * 15)
            if player.projected_whip:
                value += max(0, (1.5 - player.projected_whip) * 30)
        else:
            # Batting categories: HR, R, RBI, SB, OBP
            value += (player.projected_home_runs or 0) * 2.5
            value += (player.projected_runs or 0) * 0.6
            value += (player.projected_rbi or 0) * 0.6
            value += (player.projected_stolen_bases or 0) * 3.5
            if player.projected_obp:
                value += (player.projected_obp - 0.300) * 500
        
        # Apply risk adjustments
        risk_multiplier = 1.0
        risk_multiplier *= (1.0 - (player.injury_risk_score or 0.0) * 0.3)  # Reduce value by up to 30% for injury risk
        risk_multiplier *= (player.sample_size_confidence or 0.5)  # Reduce value for low confidence
        risk_multiplier *= (player.age_decline_factor or 1.0)  # Age decline
        
        # Apply park factor adjustments
        if is_pitcher:
            park_multiplier = player.park_factor_pitching or 1.0
        else:
            park_multiplier = player.park_factor_offense or 1.0
        
        value = value * risk_multiplier * park_multiplier
        
        return value
    
    
    def train_models(self, training_data: pd.DataFrame):
        """Train ML models on training data."""
        # Separate features and target
        feature_cols = [col for col in training_data.columns if col != 'target_player_value']
        X = training_data[feature_cols].values
        y = training_data['target_player_value'].values
        
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
        roster_before: Optional[List[Player]] = None,
        all_players: Optional[List[Player]] = None,
        pick_number: Optional[int] = None,
        round_num: Optional[int] = None,
        all_rosters: Optional[Dict[str, List[Player]]] = None
    ) -> float:
        """
        Predict player value score based on player data features only.
        NO DRAFT CONTEXT is used - purely based on player statistics and features.
        """
        if self.value_model is None:
            if not self.load_models():
                return 0.0
        
        # Extract player features (no draft context needed)
        features = self._extract_player_features(player)
        
        # Convert to array and scale
        feature_cols = list(features.keys())
        X = np.array([[features[col] for col in feature_cols]])
        X_scaled = self.scaler.transform(X)
        
        # Predict player value (higher is better)
        predicted_value = self.value_model.predict(X_scaled)[0]
        
        return predicted_value

