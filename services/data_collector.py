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
        Get fundamental data for a stock from local CSV
        
        Args:
            stock_code: Stock code
        
        Returns:
            Dictionary with fundamental metrics
        """
        try:
            csv_path = os.path.join(self.data_dir, "lq45_fundamental.csv")
            
            if not os.path.exists(csv_path):
                print(f"Warning: Fundamental CSV not found at {csv_path}")
                raise FileNotFoundError("Fundamental CSV not found")
                
            df = pd.read_csv(csv_path)
            
            # Clean stock code to match CSV format (remove .JK if present)
            clean_code = stock_code.replace(".JK", "") if stock_code.endswith(".JK") else stock_code
            
            # Ensure ticker column exists and is string
            if 'ticker' not in df.columns:
                raise ValueError("CSV missing 'ticker' column")
            df['ticker'] = df['ticker'].astype(str)
            
            stock_df = df[df['ticker'] == clean_code].copy()
            
            if stock_df.empty:
                print(f"Warning: Stock {clean_code} not found in fundamental CSV")
                raise ValueError(f"Stock {clean_code} not found in CSV")
            
            # --- FIX: Always use the LATEST available data ---
            # Step 1: Define period ranking (newest first)
            period_rank = {
                'February - July 2026': 5,
                'February - July 2025': 4,
                'February - July 2024': 3,
                '2023': 2,
                'Unknown': 1
            }
            stock_df['_period_rank'] = stock_df['pdf_period'].map(period_rank).fillna(0)
            
            # Step 2: Parse report_date (e.g. "Sep 2025") into sortable datetime
            stock_df['_report_dt'] = pd.to_datetime(stock_df['report_date'], format='%b %Y', errors='coerce')
            
            # Step 3: Sort by period rank DESC, then by report date DESC — take the absolute latest row
            stock_df = stock_df.sort_values(['_period_rank', '_report_dt'], ascending=[False, False])
            latest_data = stock_df.iloc[0]
            
            print(f"  [Fundamental] {clean_code}: Using data from period='{latest_data['pdf_period']}', report_date='{latest_data['report_date']}'")
            
            fundamental = {
                'roe': float(latest_data.get('roe', 0)),
                'per': float(latest_data.get('per', 0)),
                'der': float(latest_data.get('der', 0)),
                'eps': float(latest_data.get('eps', 0)),
                'dividend': float(latest_data.get('dividend_yield', 0)) / 100.0 if pd.notna(latest_data.get('dividend_yield')) else 0.0,
                'is_dummy': False
            }
            
            # Clean up NaNs
            for key in fundamental:
                if key == 'is_dummy': continue
                if pd.isna(fundamental[key]):
                    fundamental[key] = 0.0
                    
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