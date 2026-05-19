"""
Data collection service for stock market data
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import time

from config import DATA_DIR, LQ45_STOCKS, DATA_PERIOD, DATA_INTERVAL
from utils.helpers import save_json, load_json, get_dummy_news_data

class DataCollector:
    """Class to collect and manage stock market data"""
    
    def __init__(self):
        """Initialize data collector"""
        self.data_dir = DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
    
    def download_stock_data(self, stock_code: str, period: str = DATA_PERIOD) -> pd.DataFrame:
        """
        Download historical stock data from Yahoo Finance
        
        Args:
            stock_code: Stock code (e.g., BBRI.JK)
            period: Data period (5y, 1y, 6mo, etc.)
        
        Returns:
            DataFrame with stock data
        """
        try:
            print(f"Downloading data for {stock_code}...")
            ticker = yf.Ticker(stock_code)
            df = ticker.history(period=period, interval=DATA_INTERVAL)
            
            if df.empty:
                print(f"No data found for {stock_code}")
                return pd.DataFrame()
            
            # Reset index to make Date a column
            df.reset_index(inplace=True)
            
            # Convert Date to timezone-naive
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            
            # Save raw data
            filepath = os.path.join(self.data_dir, f"{stock_code}_raw.csv")
            df.to_csv(filepath, index=False)
            
            print(f"Successfully downloaded {len(df)} records for {stock_code}")
            return df
            
        except Exception as e:
            print(f"Error downloading data for {stock_code}: {str(e)}")
            return pd.DataFrame()
    
    def download_multiple_stocks(self, stock_codes: List[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Download data for multiple stocks
        
        Args:
            stock_codes: List of stock codes (default: LQ45_STOCKS)
        
        Returns:
            Dictionary mapping stock codes to DataFrames
        """
        if stock_codes is None:
            stock_codes = LQ45_STOCKS
        
        stock_data = {}
        for code in stock_codes:
            df = self.download_stock_data(code)
            if not df.empty:
                stock_data[code] = df
            time.sleep(0.5)  # Rate limiting
            
        return stock_data
    
    def get_fundamental_data(self, stock_code: str) -> Dict:
        """
        Get fundamental data for a stock (using Yahoo Finance)
        
        Args:
            stock_code: Stock code
        
        Returns:
            Dictionary with fundamental metrics
        """
        try:
            ticker = yf.Ticker(stock_code)
            info = ticker.info
            
            # Extract fundamental metrics with fallback to dummy values
            fundamental = {
                'roe': info.get('returnOnEquity', 0.15),
                'per': info.get('trailingPE', 15.0),
                'der': info.get('debtToEquity', 0.5),
                'eps': info.get('trailingEps', 500),
                'dividend': info.get('dividendYield', 0.03),
                'is_dummy': False
            }
            
            # Clean and convert values
            for key in fundamental:
                if key == 'is_dummy': continue
                if fundamental[key] is None:
                    fundamental[key] = 0
                elif isinstance(fundamental[key], (int, float)):
                    if key == 'roe':
                        fundamental[key] = fundamental[key] * 100 if fundamental[key] < 1 else fundamental[key]
            
            return fundamental
            
        except Exception as e:
            print(f"Error getting fundamental data for {stock_code}: {str(e)}")
            # Return empty fundamental data with flag instead of misleading dummy data
            return {
                'roe': None,
                'per': None,
                'der': None,
                'eps': None,
                'dividend': None,
                'is_dummy': True,
                'error': str(e)
            }
    
    def collect_news_data(self, stock_code: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Collect news data for a stock
        
        Note: For production, integrate with actual news API
        
        Args:
            stock_code: Stock code
            start_date: Start date for news collection
            end_date: End date for news collection
        
        Returns:
            List of news articles
        """
        # Generate dummy news for demonstration
        news_articles = []
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.day % 4 == 0:
                news = get_dummy_news_data(stock_code, current_date)
                news_articles.extend(news)
            current_date += timedelta(days=1)
        
        return news_articles
    
    def load_saved_data(self, stock_code: str) -> pd.DataFrame:
        """Load saved stock data from CSV"""
        filepath = os.path.join(self.data_dir, f"{stock_code}_raw.csv")
        if os.path.exists(filepath):
            return pd.read_csv(filepath)
        return pd.DataFrame()