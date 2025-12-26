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
        self.gradient_boosting_model = None  # Ensemble model
        self.scaler = StandardScaler()
        self.feature_columns = None  # Store feature column order from training
    
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
            
            # Add contextual features (set to 0 during training - no draft context available)
            # These will be populated during prediction with actual draft context
            features['pick_number'] = 0
            features['round'] = 0
            features['pick_in_round'] = 0
            features['position_scarcity'] = 0.0
            features['team_needs_score'] = 0.0
            features['position_scarcity_score'] = 0.0
            features['category_targeting_score'] = 0.0
            features['comparative_advantage_score'] = 0.0
            features['risk_score'] = 0.0  # Risk is already in _extract_player_features, but add for consistency
            
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
        """Extract features from player data only (no draft context).
        
        IMPORTANT: Include ALL features (both hitter and pitcher) for all players.
        Missing features are set to 0. This ensures the ML model receives the expected feature set.
        """
        is_pitcher = player.position in ['SP', 'RP', 'P']
        is_hitter = not is_pitcher
        
        features = {}
        
        # === Projections (Steamer + DepthChart average) ===
        # Include BOTH hitter and pitcher features for all players (missing = 0)
        # Hitter features
        features['hr'] = player.projected_home_runs or 0 if is_hitter else 0
        features['r'] = player.projected_runs or 0 if is_hitter else 0
        features['rbi'] = player.projected_rbi or 0 if is_hitter else 0
        features['sb'] = player.projected_stolen_bases or 0 if is_hitter else 0
        features['obp'] = player.projected_obp or 0.3 if is_hitter else 0
        
        # Pitcher features
        features['k'] = player.projected_strikeouts or 0 if is_pitcher else 0
        features['era'] = player.projected_era or 5.0 if is_pitcher else 0
        features['whip'] = player.projected_whip or 1.5 if is_pitcher else 0
        features['w'] = player.projected_wins or 0 if is_pitcher else 0
        features['sv'] = player.projected_saves or 0 if is_pitcher else 0
        
        # === Historical Stats (3-year average: 2022-2024) ===
        # Extract from _master_dict_data if available
        historical_features = self._extract_historical_features(player)
        features.update(historical_features)
        
        # === Statcast Features (from latest year) ===
        # Include BOTH hitter and pitcher Statcast features (missing = 0)
        # Hitter Statcast features
        features['exit_velocity'] = player.savant_exit_velocity or 0 if is_hitter else 0
        features['barrel_rate'] = player.savant_barrel_rate or 0 if is_hitter else 0
        features['hard_hit_rate'] = player.savant_hard_hit_rate or 0 if is_hitter else 0
        features['xba'] = player.savant_xba or 0 if is_hitter else 0
        features['xwoba'] = player.savant_xwoba or 0 if is_hitter else 0
        features['sprint_speed'] = player.savant_sprint_speed or 0 if is_hitter else 0
        
        # Pitcher Statcast features
        features['spin_rate'] = player.savant_spin_rate or 0 if is_pitcher else 0
        features['velocity'] = player.savant_velocity or 0 if is_pitcher else 0
        
        # === Projection Consensus ===
        # If we have Steamer + DepthChart, calculate consensus
        if hasattr(player, '_master_dict_data'):
            proj_data = player._master_dict_data.get('projections', {}).get('2025', {})
            steamer = proj_data.get('steamer', {})
            depthchart = proj_data.get('depthchart', {})
            
            # Include BOTH hitter and pitcher projection consensus features (missing = 0)
            # Hitter projection consensus
            if is_hitter:
                proj_hr = [v for v in [steamer.get('home_runs'), depthchart.get('home_runs')] if v is not None]
                features['avg_proj_hr'] = np.mean(proj_hr) if proj_hr else features.get('hr', 0)
                features['proj_std_hr'] = np.std(proj_hr) if len(proj_hr) > 1 else 0
            else:
                features['avg_proj_hr'] = 0
                features['proj_std_hr'] = 0
            
            # Pitcher projection consensus
            if is_pitcher:
                proj_era = [v for v in [steamer.get('era'), depthchart.get('era')] if v is not None]
                features['avg_proj_era'] = np.mean(proj_era) if proj_era else features.get('era', 0)
                features['proj_std_era'] = np.std(proj_era) if len(proj_era) > 1 else 0
            else:
                features['avg_proj_era'] = 0
                features['proj_std_era'] = 0
        else:
            # No projection data available - set to 0
            features['avg_proj_hr'] = 0
            features['proj_std_hr'] = 0
            features['avg_proj_era'] = 0
            features['proj_std_era'] = 0
        
        # === Park Factors ===
        features['park_factor'] = player.park_factor_offense or 100
        features['park_factor_hr'] = player.park_factor_hr or 100
        
        # === Risk Features (inferred from historical data) ===
        risk_features = self._extract_risk_features(player)
        features.update(risk_features)
        
        # === ADP ===
        features['adp'] = player.adp or 999
        
        # === Position ===
        features['is_hitter'] = 1.0 if is_hitter else 0.0
        features['is_pitcher'] = 1.0 if is_pitcher else 0.0
        
        return features
    
    def _extract_historical_features(self, player: Player) -> Dict[str, float]:
        """Extract historical stats features (3-year averages, trends)."""
        features = {}
        
        if not hasattr(player, '_master_dict_data'):
            return features
        
        historical_stats = player._master_dict_data.get('historical_stats', {})
        is_pitcher = player.position in ['SP', 'RP', 'P']
        
        # Get 2022-2024 stats (3-year window)
        years = ['2022', '2023', '2024']
        stats_by_year = {}
        
        for year in years:
            if year in historical_stats:
                year_data = historical_stats[year]
                stats = year_data.get('stats', {})
                if stats:
                    stats_by_year[year] = stats
        
        if not stats_by_year:
            return features
        
        # Calculate 3-year averages
        # Include BOTH hitter and pitcher historical features (missing = 0)
        # This ensures the ML model receives all expected features
        
        # Hitter historical features (set to 0 for pitchers)
        hr = [s.get('home_runs', 0) for s in stats_by_year.values() if s.get('home_runs')] if not is_pitcher else []
        runs = [s.get('runs', 0) for s in stats_by_year.values() if s.get('runs')] if not is_pitcher else []
        rbi = [s.get('rbi', 0) for s in stats_by_year.values() if s.get('rbi')] if not is_pitcher else []
        sb = [s.get('stolen_bases', 0) for s in stats_by_year.values() if s.get('stolen_bases')] if not is_pitcher else []
        obp = [s.get('on_base_percentage', 0.3) for s in stats_by_year.values() if s.get('on_base_percentage')] if not is_pitcher else []
        
        features['hist_avg_hr'] = np.mean(hr) if hr else 0
        features['hist_avg_r'] = np.mean(runs) if runs else 0
        features['hist_avg_rbi'] = np.mean(rbi) if rbi else 0
        features['hist_avg_sb'] = np.mean(sb) if sb else 0
        features['hist_avg_obp'] = np.mean(obp) if obp else 0.3
        features['hist_consistency_hr'] = 1.0 / (np.std(hr) + 0.1) if len(hr) > 1 else 0.5
        
        # Pitcher historical features (set to 0 for hitters)
        strikeouts = [s.get('strikeouts', 0) for s in stats_by_year.values() if s.get('strikeouts')] if is_pitcher else []
        era = [s.get('era', 5.0) for s in stats_by_year.values() if s.get('era')] if is_pitcher else []
        whip = [s.get('whip', 1.5) for s in stats_by_year.values() if s.get('whip')] if is_pitcher else []
        
        features['hist_avg_k'] = np.mean(strikeouts) if strikeouts else 0
        features['hist_avg_era'] = np.mean(era) if era else 5.0
        features['hist_avg_whip'] = np.mean(whip) if whip else 1.5
        features['hist_consistency_era'] = 1.0 / (np.std(era) + 0.1) if len(era) > 1 else 0.5
        
        # Trend analysis (improving vs declining)
        # Include BOTH hitter and pitcher trends (missing = 0)
        if len(stats_by_year) >= 2:
            # Hitter trend (HR)
            if not is_pitcher:
                recent_hr = stats_by_year.get('2024', {}).get('home_runs', 0)
                older_avg = np.mean([s.get('home_runs', 0) for y, s in stats_by_year.items() if y != '2024'])
                features['trend_hr'] = (recent_hr - older_avg) / (older_avg + 1) if older_avg > 0 else 0
            else:
                features['trend_hr'] = 0
            
            # Pitcher trend (K)
            if is_pitcher:
                recent_k = stats_by_year.get('2024', {}).get('strikeouts', 0)
                older_avg = np.mean([s.get('strikeouts', 0) for y, s in stats_by_year.items() if y != '2024'])
                features['trend_k'] = (recent_k - older_avg) / (older_avg + 1) if older_avg > 0 else 0
            else:
                features['trend_k'] = 0
        else:
            # No trend data available
            features['trend_hr'] = 0
            features['trend_k'] = 0
        
        return features
    
    def _extract_risk_features(self, player: Player) -> Dict[str, float]:
        """Extract risk features from historical data."""
        features = {
            'injury_risk': 0.0,
            'sample_size_confidence': 0.5,
            'age': 27.0,
            'years_of_data': 0.0
        }
        
        if not hasattr(player, '_master_dict_data'):
            return features
        
        historical_stats = player._master_dict_data.get('historical_stats', {})
        
        # Count years with data
        years_with_data = [y for y in historical_stats.keys() if y.isdigit()]
        features['years_of_data'] = len(years_with_data)
        features['sample_size_confidence'] = min(1.0, len(years_with_data) / 5.0)  # 5 years = full confidence
        
        # Check for gaps in data (potential injuries)
        if len(years_with_data) >= 2:
            years_int = sorted([int(y) for y in years_with_data])
            gaps = [years_int[i+1] - years_int[i] for i in range(len(years_int)-1)]
            if any(gap > 1 for gap in gaps):
                features['injury_risk'] = 0.3  # Data gap suggests injury
        
        # Age (if available in historical stats)
        # We don't have age in master dict yet, so default
        features['age'] = player.age or 27.0
        
        # Age decline factor (older players = higher risk)
        if features['age'] >= 32:
            features['age_decline'] = 1.0 - ((features['age'] - 32) * 0.05)
        else:
            features['age_decline'] = 1.0
        
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
        """Train ensemble ML models on training data."""
        # Separate features and target
        feature_cols = [col for col in training_data.columns if col != 'target_player_value']
        self.feature_columns = feature_cols  # Store for prediction
        X = training_data[feature_cols].copy()
        y = training_data['target_player_value'].values
        
        # Handle NaN values - fill with median for numeric columns, 0 for others
        for col in X.columns:
            if X[col].dtype in ['float64', 'int64']:
                X[col] = X[col].fillna(X[col].median() if not X[col].isna().all() else 0)
            else:
                X[col] = X[col].fillna(0)
        
        # Convert to numpy array
        X = X.values
        
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
        
        # Train Gradient Boosting (ensemble)
        print("Training Gradient Boosting model...")
        self.gradient_boosting_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.gradient_boosting_model.fit(X_train, y_train)
        
        # Evaluate both models
        rf_train_score = self.value_model.score(X_train, y_train)
        rf_test_score = self.value_model.score(X_test, y_test)
        gb_train_score = self.gradient_boosting_model.score(X_train, y_train)
        gb_test_score = self.gradient_boosting_model.score(X_test, y_test)
        
        # Ensemble prediction (weighted average: 60% RF, 40% GB)
        ensemble_train_pred = (self.value_model.predict(X_train) * 0.6 + 
                              self.gradient_boosting_model.predict(X_train) * 0.4)
        ensemble_test_pred = (self.value_model.predict(X_test) * 0.6 + 
                             self.gradient_boosting_model.predict(X_test) * 0.4)
        
        from sklearn.metrics import r2_score
        ensemble_train_score = r2_score(y_train, ensemble_train_pred)
        ensemble_test_score = r2_score(y_test, ensemble_test_pred)
        
        print(f"Random Forest - Train R²: {rf_train_score:.4f}, Test R²: {rf_test_score:.4f}")
        print(f"Gradient Boosting - Train R²: {gb_train_score:.4f}, Test R²: {gb_test_score:.4f}")
        print(f"Ensemble (60% RF, 40% GB) - Train R²: {ensemble_train_score:.4f}, Test R²: {ensemble_test_score:.4f}")
        
        # Save models
        self._save_models()
        
        return {
            'rf_train_score': rf_train_score,
            'rf_test_score': rf_test_score,
            'gb_train_score': gb_train_score,
            'gb_test_score': gb_test_score,
            'ensemble_train_score': ensemble_train_score,
            'ensemble_test_score': ensemble_test_score,
            'feature_importance': dict(zip(feature_cols, self.value_model.feature_importances_))
        }
    
    def _save_models(self):
        """Save trained models to disk."""
        model_file = self.models_dir / "value_model.pkl"
        gb_model_file = self.models_dir / "gradient_boosting_model.pkl"
        scaler_file = self.models_dir / "scaler.pkl"
        feature_cols_file = self.models_dir / "feature_columns.pkl"
        
        with open(model_file, 'wb') as f:
            pickle.dump(self.value_model, f)
        
        if self.gradient_boosting_model:
            with open(gb_model_file, 'wb') as f:
                pickle.dump(self.gradient_boosting_model, f)
        
        with open(scaler_file, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        # Save feature columns for consistent prediction
        if self.feature_columns:
            with open(feature_cols_file, 'wb') as f:
                pickle.dump(self.feature_columns, f)
        
        print(f"Models saved to {self.models_dir}")
    
    def load_models(self) -> bool:
        """Load trained models from disk."""
        model_file = self.models_dir / "value_model.pkl"
        gb_model_file = self.models_dir / "gradient_boosting_model.pkl"
        scaler_file = self.models_dir / "scaler.pkl"
        
        if not model_file.exists() or not scaler_file.exists():
            return False
        
        with open(model_file, 'rb') as f:
            self.value_model = pickle.load(f)
        
        if gb_model_file.exists():
            with open(gb_model_file, 'rb') as f:
                self.gradient_boosting_model = pickle.load(f)
        
        with open(scaler_file, 'rb') as f:
            self.scaler = pickle.load(f)
        
        # Try to load feature columns if available
        feature_cols_file = self.models_dir / "feature_columns.pkl"
        if feature_cols_file.exists():
            with open(feature_cols_file, 'rb') as f:
                self.feature_columns = pickle.load(f)
        else:
            print("WARNING: feature_columns.pkl not found. Feature order may not match training.")
        
        return True
    
    def predict_player_value(
        self,
        player: Player,
        roster_before: Optional[List[Player]] = None,
        all_players: Optional[List[Player]] = None,
        pick_number: Optional[int] = None,
        round_num: Optional[int] = None,
        all_rosters: Optional[Dict[str, List[Player]]] = None,
        recommendation_engine: Optional[object] = None,
        draft_state: Optional[object] = None,
        team_name: Optional[str] = None
    ) -> float:
        """
        Predict player value score using ensemble model.
        Includes ALL contextual factors: team needs, position scarcity, category targeting, 
        comparative advantage, risk - all baked into the ML model.
        """
        if self.value_model is None:
            if not self.load_models():
                return 0.0
        
        # Extract base player features
        features = self._extract_player_features(player)
        
        # Add draft context features (always include, use 0 if not available)
        features['pick_number'] = pick_number or 0
        features['round'] = round_num or (pick_number // 13) + 1 if pick_number else 0
        features['pick_in_round'] = (pick_number % 13) if pick_number else 0
        
        # Position scarcity at this point in draft
        if all_players and all_rosters:
            player_pos = player.position
            drafted_at_pos = sum(
                1 for roster in all_rosters.values()
                for p in roster
                if p.position == player_pos
            )
            available_at_pos = sum(
                1 for p in all_players
                if p.position == player_pos and not p.drafted
            )
            features['position_scarcity'] = drafted_at_pos / max(1, drafted_at_pos + available_at_pos)
        else:
            features['position_scarcity'] = 0.0
        
        # Add contextual factors (team needs, comparative advantage, category priorities, risk)
        # These are baked into the ML model - the model learns how to weight them
        if recommendation_engine and roster_before and draft_state and team_name:
            # Team needs score (normalized)
            try:
                needs_score, _ = recommendation_engine._analyze_team_needs(
                    player, roster_before, draft_state, all_players or []
                )
                features['team_needs_score'] = needs_score / 100.0  # Normalize to 0-1 range
            except:
                features['team_needs_score'] = 0.0
            
            # Position scarcity score (normalized)
            try:
                pos_score, _ = recommendation_engine._analyze_position_scarcity(
                    player, roster_before, all_players or [], draft_state, all_rosters or {}
                )
                features['position_scarcity_score'] = pos_score / 100.0  # Normalize
            except:
                features['position_scarcity_score'] = 0.0
            
            # Category targeting score (normalized)
            try:
                category_priorities = recommendation_engine._optimize_category_targets(
                    roster_before, all_rosters or {}, draft_state
                )
                category_score = recommendation_engine._calculate_category_target_score(
                    player, roster_before, category_priorities
                )
                features['category_targeting_score'] = category_score / 1000.0  # Normalize
            except:
                features['category_targeting_score'] = 0.0
            
            # Comparative advantage score (normalized)
            try:
                relative_score, _ = recommendation_engine._analyze_relative_advantage(
                    player, roster_before, all_rosters or {}, draft_state, all_players or [], team_name
                )
                features['comparative_advantage_score'] = relative_score / 100.0  # Normalize
            except:
                features['comparative_advantage_score'] = 0.0
            
            # Add standings-based features directly to ML model
            try:
                # Calculate current standings
                all_rosters_for_standings = {**(all_rosters or {})}
                if team_name and team_name not in all_rosters_for_standings:
                    all_rosters_for_standings[team_name] = roster_before or []
                
                standings = recommendation_engine.standings_calculator.calculate_standings(all_rosters_for_standings)
                category_points = standings.get('category_points', {})
                total_points = standings.get('total_points', {})
                
                if team_name:
                    my_total_points = total_points.get(team_name, 0)
                    max_possible_points = len(all_rosters_for_standings) * 10  # 13 teams * 10 categories
                    
                    # Normalized total points (0-1 range)
                    features['my_total_points_normalized'] = my_total_points / max_possible_points if max_possible_points > 0 else 0.0
                    
                    # Average points per category (0-1 range, normalized by max points per category)
                    my_category_points_list = []
                    for category in recommendation_engine.standings_calculator.BATTING_CATEGORIES + recommendation_engine.standings_calculator.PITCHING_CATEGORIES:
                        if category in category_points:
                            my_category_points_list.append(category_points[category].get(team_name, 0))
                    
                    if my_category_points_list:
                        avg_category_points = sum(my_category_points_list) / len(my_category_points_list)
                        max_points_per_category = len(all_rosters_for_standings)  # 13 points max per category
                        features['avg_category_points_normalized'] = avg_category_points / max_points_per_category if max_points_per_category > 0 else 0.0
                    else:
                        features['avg_category_points_normalized'] = 0.0
                else:
                    features['my_total_points_normalized'] = 0.0
                    features['avg_category_points_normalized'] = 0.0
            except:
                features['my_total_points_normalized'] = 0.0
                features['avg_category_points_normalized'] = 0.0
            
            # Risk score (normalized)
            try:
                risk_score, _ = recommendation_engine._analyze_risk_factors(player)
                features['risk_score'] = risk_score / 100.0  # Normalize
            except:
                features['risk_score'] = 0.0
        else:
            # Default values when context not available (will be 0 during training)
            features['team_needs_score'] = 0.0
            features['position_scarcity_score'] = 0.0
            features['category_targeting_score'] = 0.0
            features['comparative_advantage_score'] = 0.0
            features['risk_score'] = 0.0
        
        # Note: During training, these contextual features will be 0 (no draft context).
        # During prediction, they'll have real values. The model learns to use them when available.
        
        # Convert to array and scale using the same feature order as training
        if self.feature_columns is None:
            # Fallback: use current features (might cause mismatch)
            feature_cols = list(features.keys())
            print(f"WARNING: No feature columns stored from training. Using {len(feature_cols)} features.")
        else:
            feature_cols = self.feature_columns
        
        # Ensure all required features are present, fill missing ones with 0
        X_values = []
        for col in feature_cols:
            if col in features:
                X_values.append(features[col])
            else:
                X_values.append(0.0)  # Default value for missing features
                print(f"WARNING: Missing feature '{col}' in prediction, using 0.0")
        
        X = np.array([X_values])
        
        if X.shape[1] != len(feature_cols):
            print(f"ERROR: Feature count mismatch. Expected {len(feature_cols)}, got {X.shape[1]}")
            return 0.0
        
        X_scaled = self.scaler.transform(X)
        
        # Ensemble prediction (60% RandomForest, 40% GradientBoosting)
        rf_pred = self.value_model.predict(X_scaled)[0]
        if self.gradient_boosting_model:
            gb_pred = self.gradient_boosting_model.predict(X_scaled)[0]
            predicted_value = rf_pred * 0.6 + gb_pred * 0.4
        else:
            predicted_value = rf_pred
        
        return predicted_value

