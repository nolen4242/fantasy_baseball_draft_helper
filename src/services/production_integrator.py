"""Production integration: Loads all data and prepares for ML training and recommendations."""
from pathlib import Path
from typing import List, Dict
from src.services.master_player_dict_loader import MasterPlayerDictLoader
from src.services.ml_trainer import MLTrainer
from src.services.recommendation_engine import RecommendationEngine
from src.services.draft_service import DraftService
from src.models.player import Player
import json


class ProductionIntegrator:
    """
    Integrates all data sources for production use.
    - Loads master player dictionary
    - Trains ML models
    - Prepares recommendation engine
    """
    
    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = project_root
        
        self.loader = MasterPlayerDictLoader(project_root)
        self.ml_trainer = MLTrainer()
        self.draft_service = DraftService()
    
    def initialize_production(self, train_ml: bool = True) -> Dict:
        """
        Initialize production system with all data.
        
        Args:
            train_ml: Whether to train ML models (if not already trained)
        
        Returns:
            Dict with initialization report
        """
        print("=" * 60)
        print("Initializing Production System")
        print("=" * 60)
        
        # Step 1: Load all players from master dict
        print("\n1. Loading master player dictionary...")
        all_players = self.loader.load_all_players()
        print(f"   ✅ Loaded {len(all_players)} players")
        
        # Step 2: Load category thresholds for value calculation
        print("\n2. Loading league analysis data...")
        category_thresholds = self._load_category_thresholds()
        print(f"   ✅ Loaded category thresholds")
        
        # Step 3: Train ML models (if needed)
        if train_ml:
            print("\n3. Training ML models...")
            training_result = self._train_ml_models(all_players, category_thresholds)
            print(f"   ✅ ML models trained")
            print(f"      Train R²: {training_result.get('train_score', 0):.4f}")
            print(f"      Test R²: {training_result.get('test_score', 0):.4f}")
        else:
            print("\n3. Skipping ML training (use train_ml=True to train)")
            training_result = {}
        
        # Step 4: Initialize recommendation engine
        print("\n4. Initializing recommendation engine...")
        recommendation_engine = RecommendationEngine(self.draft_service, all_players)
        if train_ml:
            recommendation_engine._ml_models_loaded = True
        
        print("\n✅ Production system initialized!")
        
        return {
            'players_loaded': len(all_players),
            'ml_trained': train_ml,
            'ml_scores': training_result,
            'recommendation_engine': recommendation_engine,
            'all_players': all_players
        }
    
    def _load_category_thresholds(self) -> Dict[str, float]:
        """Load category thresholds from league analysis."""
        thresholds_file = self.project_root / "data" / "league_analysis" / "category_thresholds" / "category_thresholds.json"
        
        if not thresholds_file.exists():
            return {}
        
        with open(thresholds_file, 'r') as f:
            data = json.load(f)
        
        # Extract "to_win" thresholds
        thresholds = {}
        for category, values in data.items():
            if isinstance(values, dict) and 'to_win' in values:
                thresholds[category] = values['to_win']
        
        return thresholds
    
    def _train_ml_models(self, all_players: List[Player], category_thresholds: Dict[str, float]) -> Dict:
        """Train ML models on all player data."""
        # Generate training data
        training_data = self.ml_trainer.generate_training_data(
            all_players,
            league_thresholds=category_thresholds
        )
        
        # Train models
        result = self.ml_trainer.train_models(training_data)
        
        return result



