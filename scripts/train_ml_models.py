#!/usr/bin/env python3
"""
Train ML models for draft recommendations.

This script:
1. Loads all players from the master player dictionary
2. Generates training data from player features
3. Trains RandomForest and GradientBoosting models
4. Saves models to ml/models/
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.ml_trainer import MLTrainer
from src.services.master_player_dict_loader import MasterPlayerDictLoader


def main():
    print("=" * 60)
    print("ML Model Training for Draft Recommendations")
    print("=" * 60)
    print()
    
    # Load all players
    print("Step 1: Loading players from master dictionary...")
    loader = MasterPlayerDictLoader()
    all_players = loader.load_all_players()
    
    if not all_players:
        print("❌ ERROR: No players loaded. Make sure you have:")
        print("   - Master player dictionary files in data/batters/ and data/pitchers/")
        print("   - Or run the data loading scripts first")
        return 1
    
    print(f"✅ Loaded {len(all_players)} players")
    print()
    
    # Initialize ML trainer
    print("Step 2: Initializing ML trainer...")
    trainer = MLTrainer()
    print(f"✅ Models will be saved to: {trainer.models_dir}")
    print()
    
    # Generate training data
    print("Step 3: Generating training data from player features...")
    training_data = trainer.generate_training_data(all_players)
    
    if training_data.empty:
        print("❌ ERROR: No training data generated. Check player data.")
        return 1
    
    print(f"✅ Generated {len(training_data)} training samples")
    print(f"   Features: {len(training_data.columns) - 1} (excluding target)")
    print()
    
    # Train models
    print("Step 4: Training ML models...")
    print("   This may take a few minutes...")
    print()
    
    results = trainer.train_models(training_data)
    
    print()
    print("=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print()
    print("Model Performance:")
    print(f"  Random Forest - Train R²: {results['rf_train_score']:.4f}, Test R²: {results['rf_test_score']:.4f}")
    print(f"  Gradient Boosting - Train R²: {results['gb_train_score']:.4f}, Test R²: {results['gb_test_score']:.4f}")
    print(f"  Ensemble - Train R²: {results['ensemble_train_score']:.4f}, Test R²: {results['ensemble_test_score']:.4f}")
    print()
    print("Top 10 Most Important Features:")
    feature_importance = sorted(results['feature_importance'].items(), key=lambda x: x[1], reverse=True)
    for i, (feature, importance) in enumerate(feature_importance[:10], 1):
        print(f"  {i:2d}. {feature:30s} {importance:.4f}")
    print()
    print(f"✅ Models saved to {trainer.models_dir}")
    print()
    print("The recommendation engine will now use these models!")
    
    return 0


if __name__ == "__main__":
    exit(main())

