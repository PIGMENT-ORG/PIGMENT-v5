#!/usr/bin/env python3
"""
PIGMENT v5 - Model Training Script
Retrains the Ultimate AI model from collected training data
"""

import os
import sys
import json
import glob
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class PigmentModelTrainer:
    def __init__(self, data_dir='training_data', models_dir='models'):
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.feature_names = [
            'fitness', 'density', 'is_stuck', 'polyRatio',
            'mean_r', 'mean_g', 'mean_b', 'brightness_mean', 'brightness_std'
        ]
        
        # Create directories if they don't exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)
        
    def load_training_data(self):
        """Load all training data from JSON files"""
        print("📂 Loading training data...")
        
        metadata_files = glob.glob(f"{self.data_dir}/metadata_*.json")
        if not metadata_files:
            print("⚠️ No training data found")
            return None, None
        
        X_list = []
        y_list = []
        
        for f in metadata_files:
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                
                if 'features' in data and 'fitness' in data:
                    X_list.append(data['features'])
                    y_list.append(data['fitness'])
            except Exception as e:
                print(f"⚠️ Error loading {f}: {e}")
        
        if not X_list:
            print("⚠️ No valid training data found")
            return None, None
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        print(f"✅ Loaded {len(X)} training samples")
        print(f"   Feature dimension: {X.shape[1]}")
        print(f"   Fitness range: {y.min():.2f} - {y.max():.2f}")
        
        return X, y
    
    def train_model(self, X, y):
        """Train the gradient boosting model"""
        print("\n🧠 Training model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            subsample=0.8,
            min_samples_split=5,
            random_state=42,
            verbose=True
        )
        
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_score = model.score(X_train_scaled, y_train)
        test_score = model.score(X_test_scaled, y_test)
        
        print(f"\n📊 Model Performance:")
        print(f"   Train R²: {train_score:.4f}")
        print(f"   Test R²:  {test_score:.4f}")
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': self.feature_names[:len(model.feature_importances_)],
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n📈 Feature Importance:")
        for _, row in importance.iterrows():
            print(f"   {row['feature']:20s}: {row['importance']:.4f}")
        
        return model, scaler
    
    def save_model(self, model, scaler, version=None):
        """Save model with versioning"""
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save with version
        model_data = {
            'model': model,
            'scaler': scaler,
            'feature_names': self.feature_names,
            'version': version,
            'timestamp': datetime.now().isoformat()
        }
        
        model_path = f"{self.models_dir}/ultimate_pigment_ai_{version}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Update latest symlink
        latest_path = f"{self.models_dir}/ultimate_pigment_ai.pkl"
        if os.path.exists(latest_path):
            os.remove(latest_path)
        
        # Create symlink or copy
        import shutil
        shutil.copy(model_path, latest_path)
        
        print(f"\n✅ Model saved: {model_path}")
        print(f"✅ Latest model updated: {latest_path}")
        
        return model_path
    
    def retrain(self, force=False):
        """Main retraining pipeline"""
        print("=" * 50)
        print("🚀 PIGMENT Model Retraining")
        print("=" * 50)
        
        # Load data
        X, y = self.load_training_data()
        if X is None or len(X) < 50:
            print("❌ Insufficient training data (need at least 50 samples)")
            return None
        
        # Train model
        model, scaler = self.train_model(X, y)
        
        # Save model
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.save_model(model, scaler, version)
        
        # Generate training report
        self.generate_report(X, y, version)
        
        return model_path
    
    def generate_report(self, X, y, version):
        """Generate training report"""
        report = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'samples': len(X),
            'feature_dim': X.shape[1],
            'fitness_stats': {
                'min': float(y.min()),
                'max': float(y.max()),
                'mean': float(y.mean()),
                'std': float(y.std())
            }
        }
        
        report_path = f"{self.models_dir}/training_report_{version}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📝 Training report saved: {report_path}")
        return report

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Retrain PIGMENT AI model')
    parser.add_argument('--force', action='store_true', help='Force retrain even with few samples')
    parser.add_argument('--data-dir', default='training_data', help='Training data directory')
    parser.add_argument('--models-dir', default='models', help='Models output directory')
    
    args = parser.parse_args()
    
    trainer = PigmentModelTrainer(data_dir=args.data_dir, models_dir=args.models_dir)
    trainer.retrain(force=args.force)

if __name__ == '__main__':
    main()
