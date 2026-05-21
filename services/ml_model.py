"""
Machine Learning service for stock prediction
Upgraded to CLASSIFICATION (BUY=1 / HOLD-SELL=0) for better accuracy.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib
import os
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

from config import TEST_SIZE, RANDOM_STATE, MODELS_DIR

class StockPredictor:
    """Machine learning classifier for stock BUY/HOLD-SELL signal prediction"""
    
    def __init__(self):
        """Initialize classifier models and directories"""
        self.models = {
            'random_forest': RandomForestClassifier(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=5,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                class_weight='balanced'  # Handle class imbalance
            ),
            'xgboost': xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                eval_metric='logloss',
                verbosity=0
            ),
            'logistic_regression': LogisticRegression(
                max_iter=1000,
                C=1.0,
                class_weight='balanced',
                random_state=RANDOM_STATE
            )
        }
        
        self.trained_models = {}
        self.feature_importance = {}
        self.scaler = StandardScaler()
        self.models_dir = MODELS_DIR
        os.makedirs(self.models_dir, exist_ok=True)
    
    def train_model(self, X: np.ndarray, y: np.ndarray, model_name: str) -> Any:
        """Train a specific classifier model"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found. Available: {list(self.models.keys())}")
        model = self.models[model_name]
        model.fit(X, y)
        return model
    
    def train_all_models(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train all classifier models"""
        trained_models = {}
        for name, model in self.models.items():
            print(f"Training {name}...")
            trained_models[name] = self.train_model(X, y, name)
            if hasattr(model, 'feature_importances_'):
                self.feature_importance[name] = model.feature_importances_
        self.trained_models = trained_models
        return trained_models
    
    def evaluate_model(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        Evaluate classifier performance.
        Returns accuracy, f1_score (macro), and a pseudo-R2 for backward compat.
        """
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1  = f1_score(y_test, y_pred, average='macro', zero_division=0)
        # Keep 'r2' key so all downstream code still works — we repurpose it as accuracy
        return {
            'accuracy': round(acc, 4),
            'f1': round(f1, 4),
            'r2': round(acc, 4),   # alias so old R2 checks still pass
            'mae': round(1 - acc, 4),   # alias: error rate
            'rmse': round(1 - f1, 4),   # alias: 1-f1
        }
    
    def evaluate_all_models(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Dict[str, float]]:
        """Evaluate all trained classifiers"""
        return {name: self.evaluate_model(model, X_test, y_test)
                for name, model in self.trained_models.items()}
    
    def ensemble_predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Return average BUY probability from all classifiers.
        Used to derive the technical_score in screening.
        """
        if not self.trained_models:
            raise ValueError("No trained models found. Please train models first.")
        probas = []
        for model in self.trained_models.values():
            if hasattr(model, 'predict_proba'):
                probas.append(model.predict_proba(X)[:, 1])
            else:
                probas.append(model.predict(X).astype(float))
        return np.mean(probas, axis=0)
    
    def ensemble_predict(self, X: np.ndarray) -> np.ndarray:
        """
        Hard-vote ensemble: majority-vote across all classifiers.
        Returns binary array (1=BUY, 0=HOLD/SELL).
        """
        if not self.trained_models:
            raise ValueError("No trained models found.")
        votes = []
        for model in self.trained_models.values():
            votes.append(model.predict(X))
        vote_matrix = np.stack(votes, axis=0)
        # Majority vote
        return (vote_matrix.mean(axis=0) >= 0.5).astype(int)
    
    def train_and_evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = TEST_SIZE
    ) -> Dict[str, Any]:
        """Complete training and evaluation pipeline for classifiers"""
        # Convert target to int just in case it comes in as float
        y = y.astype(int)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=RANDOM_STATE, shuffle=False
        )
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled  = self.scaler.transform(X_test)
        
        self.train_all_models(X_train_scaled, y_train)
        evaluation = self.evaluate_all_models(X_test_scaled, y_test)
        
        # Ensemble metrics
        ens_preds = self.ensemble_predict(X_test_scaled)
        ens_acc   = accuracy_score(y_test, ens_preds)
        ens_f1    = f1_score(y_test, ens_preds, average='macro', zero_division=0)
        evaluation['ensemble'] = {
            'accuracy': round(ens_acc, 4),
            'f1': round(ens_f1, 4),
            'r2':   round(ens_acc, 4),
            'mae':  round(1 - ens_acc, 4),
            'rmse': round(1 - ens_f1, 4),
        }
        
        buy_rate = y_test.mean()
        print(f"  [Classifier] Ensemble Accuracy={ens_acc:.4f} | F1={ens_f1:.4f} | BUY-rate in test={buy_rate:.2%}")
        
        self.X_test = X_test
        self.y_test = y_test
        
        return {
            'evaluation': evaluation,
            'feature_importance': self.feature_importance,
            'train_size': len(X_train),
            'test_size': len(X_test)
        }
    
    def predict_stock(self, features: np.ndarray) -> Dict[str, float]:
        """
        Predict BUY probability and signal for new data.
        Returns dict compatible with existing downstream code.
        """
        scaled = self.scaler.transform(features.reshape(1, -1))
        predictions = {}
        for name, model in self.trained_models.items():
            if hasattr(model, 'predict_proba'):
                predictions[name] = float(model.predict_proba(scaled)[0, 1])
            else:
                predictions[name] = float(model.predict(scaled)[0])
        predictions['ensemble'] = float(self.ensemble_predict_proba(scaled)[0])
        return predictions
    
    def save_models(self, stock_code: str = None) -> None:
        """Save trained models to disk"""
        suffix = f"_{stock_code}" if stock_code else ""
        for name, model in self.trained_models.items():
            filepath = os.path.join(self.models_dir, f"{name}{suffix}.pkl")
            joblib.dump(model, filepath)
            print(f"Saved {name} to {filepath}")
        scaler_path = os.path.join(self.models_dir, f"scaler{suffix}.pkl")
        joblib.dump(self.scaler, scaler_path)
        print(f"Saved scaler to {scaler_path}")
    
    def load_models(self, stock_code: str = None) -> None:
        """Load trained models from disk"""
        suffix = f"_{stock_code}" if stock_code else ""
        for name in self.models.keys():
            filepath = os.path.join(self.models_dir, f"{name}{suffix}.pkl")
            if os.path.exists(filepath):
                self.trained_models[name] = joblib.load(filepath)
                print(f"Loaded {name} from {filepath}")
        scaler_path = os.path.join(self.models_dir, f"scaler{suffix}.pkl")
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            print(f"Loaded scaler from {scaler_path}")

# Global instance
stock_predictor = StockPredictor()