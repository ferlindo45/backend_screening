"""
Feature engineering service for stock data
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

from config import MA_WINDOWS, VOLATILITY_WINDOW, TARGET_WINDOW, FEATURE_COLUMNS, TARGET_COLUMN

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """Class for creating technical and fundamental features"""
    
    def __init__(self):
        """Initialize feature engineer"""
        self.ma_windows = MA_WINDOWS
        self.volatility_window = VOLATILITY_WINDOW
        self.target_window = TARGET_WINDOW
    
    def calculate_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate professional technical indicators
        """
        df = df.copy()
        
        # 1. Moving Averages (Basic & Professional)
        windows = [5, 10, 20, 50, 100, 200]
        for w in windows:
            df[f'ma{w}'] = df['Close'].rolling(window=w).mean()
            df[f'ema{w}'] = df['Close'].ewm(span=w, adjust=False).mean()

        # 2. Daily returns & Volatility
        df['return'] = df['Close'].pct_change()
        df['volatility'] = df['return'].rolling(window=20).std()
        
        # 3. RSI (Relative Strength Index) - Period 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. MACD (Moving Average Convergence Divergence)
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd_line'] = ema12 - ema26
        df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['macd_signal']
        
        # 5. Bollinger Bands (20, 2)
        df['bb_mid'] = df['ma20']
        df['bb_std'] = df['Close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
        
        # 6. Momentum & Volume (Professional)
        df['momentum'] = df['Close'].pct_change(periods=10)
        df['volume_ma20'] = df['Volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_ma20']
        
        # 6a. VWAP (Volume Weighted Average Price) - Daily approximation
        df['vwap'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
        
        # 6b. OBV (On-Balance Volume)
        df['obv'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        
        # 6c. ATR (Average True Range) for Volatility
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()
        
        # 7. Support & Resistance (Local Min/Max)
        df['resistance'] = df['High'].rolling(window=20).max()
        df['support'] = df['Low'].rolling(window=20).min()
        
        # 8. Golden/Death Cross
        df['golden_cross'] = (df['ma50'] > df['ma200']).astype(int)
        
        return df
    
    def calculate_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate target variable (future return)
        
        Args:
            df: DataFrame with technical features
        
        Returns:
            DataFrame with target column added
        """
        df = df.copy()
        
        # Future return over target_window days
        df[TARGET_COLUMN] = df['Close'].shift(-self.target_window) / df['Close'] - 1
        
        return df
    
    def add_fundamental_features(self, df: pd.DataFrame, fundamental_data: Dict) -> pd.DataFrame:
        """
        Add fundamental data to the feature set
        
        Args:
            df: DataFrame with technical features
            fundamental_data: Dictionary of fundamental metrics
        
        Returns:
            DataFrame with fundamental features added
        """
        df = df.copy()
        
        # Add fundamental metrics (constant across time for simplicity)
        df['roe'] = fundamental_data.get('roe', 0)
        df['per'] = fundamental_data.get('per', 0)
        df['der'] = fundamental_data.get('der', 0)
        df['eps'] = fundamental_data.get('eps', 0)
        df['dividend'] = fundamental_data.get('dividend', 0)
        
        return df
    
    def add_sentiment_features(self, df: pd.DataFrame, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add sentiment features to the dataset
        
        Args:
            df: DataFrame with other features
            sentiment_df: DataFrame with daily sentiment scores
        
        Returns:
            DataFrame with sentiment features added
        """
        if sentiment_df is None or sentiment_df.empty:
            df['sentiment_score'] = 0
            df['sentiment_trend'] = 0
            return df
        
        df = df.copy()
        
        # Ensure date columns are timezone-naive
        if 'Date' in df.columns:
            df['date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        else:
            df['date'] = pd.to_datetime(df.index).tz_localize(None)
        
        # Ensure sentiment_df date is timezone-naive
        sentiment_df = sentiment_df.copy()
        sentiment_df['date'] = pd.to_datetime(sentiment_df['date']).dt.tz_localize(None)
        
        # Merge on date
        df = df.merge(
            sentiment_df[['date', 'sentiment_score']],
            on='date',
            how='left'
        )
        
        # Fill missing sentiment with neutral
        df['sentiment_score'] = df['sentiment_score'].fillna(0)
        
        # Calculate sentiment trend (rolling average)
        df['sentiment_trend'] = df['sentiment_score'].rolling(window=5).mean()
        
        # Drop the temporary date column if it wasn't originally there
        if 'Date' not in df.columns and 'date' in df.columns:
            df = df.drop('date', axis=1)
        
        return df
    
    def clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and prepare features for ML model
        
        Args:
            df: DataFrame with all features
        
        Returns:
            Cleaned DataFrame ready for modeling
        """
        df = df.copy()
        
        # Drop rows with NaN in target or important features
        required_cols = [col for col in FEATURE_COLUMNS if col in df.columns]
        required_cols.append(TARGET_COLUMN)
        
        # Debug info
        print(f"clean_features: before dropna, shape={df.shape}")
        print(f"  Required columns: {required_cols}")
        
        df = df.dropna(subset=required_cols)
        print(f"clean_features: after dropna, shape={df.shape}")
        
        # Remove infinite values
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna()
        
        return df
    
    def prepare_features_for_model(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, list]:
        """
        Prepare features and target for model training
        
        Args:
            df: DataFrame with all features
        
        Returns:
            Tuple of (X_features, y_target, feature_names)
        """
        # Select feature columns that exist in DataFrame
        available_features = [col for col in FEATURE_COLUMNS if col in df.columns]
        
        X = df[available_features].values
        y = df[TARGET_COLUMN].values
        
        return X, y, available_features
    
    def create_complete_dataset(
        self,
        stock_data: pd.DataFrame,
        fundamental_data: Dict,
        sentiment_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Create complete feature dataset for a stock
        
        Args:
            stock_data: Raw OHLCV data
            fundamental_data: Fundamental metrics
            sentiment_data: Daily sentiment scores (optional)
        
        Returns:
            Complete DataFrame with all features
        """
        # FIX: Check minimum data requirement
        min_required_rows = max(self.ma_windows) + self.target_window + 10
        if len(stock_data) < min_required_rows:
            print(f"WARNING: Insufficient data for {len(stock_data)} rows. Need at least {min_required_rows} rows")
            print(f"  Using available data but features may have many NaN values")
        
        # Calculate technical features
        df = self.calculate_technical_features(stock_data)
        
        # Calculate target
        df = self.calculate_target(df)
        
        # Add fundamental features
        df = self.add_fundamental_features(df, fundamental_data)
        
        # Add sentiment features if available
        if sentiment_data is not None and not sentiment_data.empty:
            df = self.add_sentiment_features(df, sentiment_data)
        else:
            df['sentiment_score'] = 0
            df['sentiment_trend'] = 0
        
        # Clean the dataset
        df = self.clean_features(df)
        
        print(f"create_complete_dataset: input {len(stock_data)} rows, output {len(df)} rows")
        
        return df