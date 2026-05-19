"""
Machine Learning service for stock prediction
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib
import os
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

from config import TEST_SIZE, RANDOM_STATE, MODELS_DIR

class StockPredictor:
    """Machine learning model for stock prediction"""
    
    def __init__(self):
        """Initialize models and directories"""
        self.models = {
            'random_forest': RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=RANDOM_STATE,
                n_jobs=-1
            ),
            'xgboost': xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=RANDOM_STATE,
                n_jobs=-1
            ),
            'linear_regression': LinearRegression()
        }
        
        self.trained_models = {}
        self.feature_importance = {}
        self.scaler = StandardScaler()
        self.models_dir = MODELS_DIR
        os.makedirs(self.models_dir, exist_ok=True)
    
    def train_model(self, X: np.ndarray, y: np.ndarray, model_name: str) -> Any:
        """
        Train a specific model
        
        Args:
            X: Feature matrix
            y: Target vector
            model_name: Name of the model to train
        
        Returns:
            Trained model
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found. Available: {list(self.models.keys())}")
        
        model = self.models[model_name]
        model.fit(X, y)
        
        return model
    
    def train_all_models(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Train all models
        
        Args:
            X: Feature matrix
            y: Target vector
        
        Returns:
            Dictionary of trained models
        """
        trained_models = {}
        
        for name, model in self.models.items():
            print(f"Training {name}...")
            trained_models[name] = self.train_model(X, y, name)
            
            # Store feature importance for tree-based models
            if hasattr(model, 'feature_importances_'):
                self.feature_importance[name] = model.feature_importances_
        
        self.trained_models = trained_models
        return trained_models
    
    def evaluate_model(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model performance
        
        Args:
            model: Trained model
            X_test: Test features
            y_test: Test target
        
        Returns:
            Dictionary with evaluation metrics
        """
        y_pred = model.predict(X_test)
        
        metrics = {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred)
        }
        
        return metrics
    
    def evaluate_all_models(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Dict[str, float]]:
        """
        Evaluate all trained models
        
        Args:
            X_test: Test features
            y_test: Test target
        
        Returns:
            Dictionary of evaluation metrics for each model
        """
        evaluation_results = {}
        
        for name, model in self.trained_models.items():
            evaluation_results[name] = self.evaluate_model(model, X_test, y_test)
        
        return evaluation_results
    
    def ensemble_predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using ensemble of all models
        
        Args:
            X: Feature matrix
        
        Returns:
            Ensemble predictions (average of all models)
        """
        if not self.trained_models:
            raise ValueError("No trained models found. Please train models first.")
        
        predictions = []
        
        for model in self.trained_models.values():
            pred = model.predict(X)
            predictions.append(pred)
        
        # Average predictions
        ensemble_pred = np.mean(predictions, axis=0)
        
        return ensemble_pred
    
    def train_and_evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = TEST_SIZE
    ) -> Dict[str, Any]:
        """
        Complete training and evaluation pipeline
        
        Args:
            X: Feature matrix
            y: Target vector
            test_size: Proportion of data for testing
        
        Returns:
            Dictionary with training results
        """
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=RANDOM_STATE, shuffle=False
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train all models
        self.train_all_models(X_train_scaled, y_train)
        
        # Evaluate all models
        evaluation = self.evaluate_all_models(X_test_scaled, y_test)
        
        # Make ensemble predictions on test set
        ensemble_predictions = self.ensemble_predict(X_test_scaled)
        
        # Calculate ensemble metrics
        ensemble_metrics = {
            'mae': mean_absolute_error(y_test, ensemble_predictions),
            'rmse': np.sqrt(mean_squared_error(y_test, ensemble_predictions)),
            'r2': r2_score(y_test, ensemble_predictions)
        }
        
        evaluation['ensemble'] = ensemble_metrics
        
        # Store test data for reference
        self.X_test = X_test
        self.y_test = y_test
        self.ensemble_predictions = ensemble_predictions
        
        return {
            'evaluation': evaluation,
            'feature_importance': self.feature_importance,
            'train_size': len(X_train),
            'test_size': len(X_test)
        }
    
    def predict_stock(self, features: np.ndarray) -> Dict[str, float]:
        """
        Predict stock returns for new data
        
        Args:
            features: Feature matrix for prediction
        
        Returns:
            Dictionary with individual model predictions and ensemble
        """
        # Scale input features
        scaled_features = self.scaler.transform(features.reshape(1, -1))
        
        predictions = {}
        
        # Individual model predictions
        for name, model in self.trained_models.items():
            predictions[name] = float(model.predict(scaled_features)[0])
        
        # Ensemble prediction
        predictions['ensemble'] = float(self.ensemble_predict(scaled_features)[0])
        
        return predictions
    
    def save_models(self, stock_code: str = None) -> None:
        """
        Save trained models to disk
        
        Args:
            stock_code: Optional stock code for naming
        """
        suffix = f"_{stock_code}" if stock_code else ""
        
        for name, model in self.trained_models.items():
            filepath = os.path.join(self.models_dir, f"{name}{suffix}.pkl")
            joblib.dump(model, filepath)
            print(f"Saved {name} model to {filepath}")
            
        # Save scaler
        scaler_path = os.path.join(self.models_dir, f"scaler{suffix}.pkl")
        joblib.dump(self.scaler, scaler_path)
        print(f"Saved scaler to {scaler_path}")
    
    def load_models(self, stock_code: str = None) -> None:
        """
        Load trained models from disk
        
        Args:
            stock_code: Optional stock code for naming
        """
        suffix = f"_{stock_code}" if stock_code else ""
        
        for name in self.models.keys():
            filepath = os.path.join(self.models_dir, f"{name}{suffix}.pkl")
            if os.path.exists(filepath):
                self.trained_models[name] = joblib.load(filepath)
                print(f"Loaded {name} model from {filepath}")
            else:
                print(f"Model {name} not found at {filepath}")
                
        # Load scaler
        scaler_path = os.path.join(self.models_dir, f"scaler{suffix}.pkl")
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            print(f"Loaded scaler from {scaler_path}")

# Global instance
stock_predictor = StockPredictor()