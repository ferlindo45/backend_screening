"""
Helper utilities for the stock screening system
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

def save_json(data: Any, filepath: str) -> None:
    """Save data to JSON file"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(filepath: str) -> Any:
    """Load data from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_fundamental_scores(roe: float, per: float, der: float, eps: float) -> float:
    """
    Calculate fundamental score based on key metrics
    
    Args:
        roe: Return on Equity (%)
        per: Price to Earnings Ratio
        der: Debt to Equity Ratio
        eps: Earnings Per Share
    
    Returns:
        Normalized fundamental score (0-1)
    """
    scores = []
    
    # ROE score (higher is better, typical range 0-30%)
    roe_score = min(max(roe / 30.0, 0), 1) if roe > 0 else 0
    scores.append(roe_score)
    
    # PER score (lower is better for value, typical range 5-25)
    if per > 0:
        per_score = max(1 - (per - 5) / 20, 0) if per > 5 else 1
        per_score = min(per_score, 1)
    else:
        per_score = 0
    scores.append(per_score)
    
    # DER score (lower is better, typical range 0-2)
    der_score = max(1 - der / 2, 0) if der > 0 else 1
    der_score = min(der_score, 1)
    scores.append(der_score)
    
    # EPS score (higher is better, normalize based on positive values)
    eps_score = min(max(eps / 1000, 0), 1) if eps > 0 else 0
    scores.append(eps_score)
    
    return np.mean(scores)

def get_dummy_news_data(stock_code: str, date: datetime) -> List[Dict]:
    """
    Generate dummy news data for demonstration
    
    Args:
        stock_code: Stock code (e.g., BBRI.JK)
        date: Date for news
    
    Returns:
        List of news articles
    """
    # Remove .JK suffix for display
    stock_name = stock_code.replace('.JK', '')
    
    dummy_news = [
        {
            "title": f"{stock_name} Catatkan Kinerja Positif di Tengah Volatilitas Pasar",
            "content": f"Perusahaan {stock_name} berhasil mencatatkan pertumbuhan laba bersih yang signifikan pada kuartal terakhir. Pendapatan meningkat 15% dibanding periode sebelumnya.",
            "date": date.strftime("%Y-%m-%d"),
            "source": "Kontan"
        },
        {
            "title": f"Analis Rekomendasikan Buy untuk Saham {stock_name}",
            "content": f"Berdasarkan prospek bisnis yang cerah, analis merekomendasikan pembelian saham {stock_name} dengan target harga lebih tinggi.",
            "date": date.strftime("%Y-%m-%d"),
            "source": "Bisnis Indonesia"
        },
        {
            "title": f"{stock_name} Ekspansi Bisnis ke Pasar Baru",
            "content": f"Perusahaan {stock_name} mengumumkan rencana ekspansi ke pasar baru yang akan meningkatkan pendapatan perusahaan secara signifikan.",
            "date": date.strftime("%Y-%m-%d"),
            "source": "CNBC Indonesia"
        }
    ]
    
    return dummy_news

def create_date_range(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Create a list of dates between start_date and end_date"""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates

def validate_stock_data(df: pd.DataFrame) -> bool:
    """Validate stock data for required columns and values"""
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    
    # Check required columns
    if not all(col in df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        print(f"Missing columns: {missing}")
        return False
    
    # Check for empty data
    if df.empty:
        print("DataFrame is empty")
        return False
    
    # Check for NaN values
    if df[required_columns].isna().any().any():
        print("Contains NaN values")
        return False
    
    return True

def convert_to_native(obj):
    """
    Recursively convert numpy types to Python native types for JSON serialization.
    Compatible with NumPy 2.0.
    """
    if obj is None:
        return None
    # Boolean
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    # Integer types
    if isinstance(obj, (np.int8, np.int16, np.int32, np.int64, np.integer)):
        return int(obj)
    # Float types
    if isinstance(obj, (np.float16, np.float32, np.float64, np.floating)):
        return float(obj)
    # Array / List / Tuple
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [convert_to_native(item) for item in obj]
    # Dictionary
    if isinstance(obj, dict):
        return {str(k): convert_to_native(v) for k, v in obj.items()}
    return obj