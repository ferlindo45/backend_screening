import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Stock configuration (Dynamically loaded from CSV)
LQ45_STOCKS = []
try:
    import pandas as pd
    _data_dir = os.getenv("DATA_DIR", "data/stock_data")
    _csv_path = os.path.join(_data_dir, "lq45_fundamental.csv")
    if os.path.exists(_csv_path):
        _df_lq = pd.read_csv(_csv_path)
        if 'ticker' in _df_lq.columns:
            _raw_tickers = _df_lq['ticker'].dropna().unique().tolist()
            LQ45_STOCKS = [f"{t}.JK" if not str(t).endswith('.JK') else str(t) for t in _raw_tickers]
except Exception as e:
    print(f"Warning: Could not load dynamic LQ45 list ({e}).")

if not LQ45_STOCKS:
    LQ45_STOCKS = [
        'AADI.JK', 'ADMR.JK', 'ADRO.JK', 'AKRA.JK', 'AMMN.JK',
        'AMRT.JK', 'ANTM.JK', 'ASII.JK', 'BBCA.JK', 'BBNI.JK',
        'BBRI.JK', 'BBTN.JK', 'BMRI.JK', 'BREN.JK', 'BRPT.JK',
        'BUMI.JK', 'CPIN.JK', 'CTRA.JK', 'DSSA.JK', 'EMTK.JK',
        'EXCL.JK', 'GOTO.JK', 'HEAL.JK', 'ICBP.JK', 'INCO.JK',
        'INDF.JK', 'INKP.JK', 'ISAT.JK', 'ITMG.JK', 'JPFA.JK',
        'KLBF.JK', 'MAPI.JK', 'MBMA.JK', 'MDKA.JK', 'MEDC.JK',
        'NCKL.JK', 'PGAS.JK', 'PGEO.JK', 'PTBA.JK', 'SCMA.JK',
        'SMGR.JK', 'TLKM.JK', 'TOWR.JK', 'UNTR.JK', 'UNVR.JK'
    ]

# Data collection period
DATA_PERIOD = '5y'
DATA_INTERVAL = '1d'

# Technical indicators parameters
MA_WINDOWS = [5, 20, 50]
VOLATILITY_WINDOW = 20
TARGET_WINDOW = 7  # days forward

# Model parameters
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Sentiment analysis
SENTIMENT_MODEL = "indobenchmark/indobert-base-p2"
MAX_SEQUENCE_LENGTH = 512

# API configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"
API_KEY = os.getenv("API_KEY", "your-secret-api-key-here")

# File paths
DATA_DIR = os.getenv("DATA_DIR", "data/stock_data")
MODELS_DIR = os.getenv("MODELS_DIR", "models/saved_models")

# Database configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "python_api_db")
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# Feature columns — must match what calculate_technical_features() produces
# Expanding from 12 → 22 columns to leverage all computed technical indicators
FEATURE_COLUMNS = [
    # Price & Returns
    'return', 'momentum', 'volatility',
    # Moving Averages
    'ma5', 'ma20', 'ma50',
    # RSI
    'rsi',
    # MACD
    'macd_line', 'macd_signal', 'macd_hist',
    # Bollinger Bands
    'bb_upper', 'bb_lower',
    # Volume Indicators
    'volume_ratio', 'obv',
    # Volatility
    'atr',
    # Trend
    'golden_cross',
    # Sentiment (from news)
    'sentiment_score',
    # Fundamentals (time-aware)
    'roe', 'per', 'der', 'eps', 'dividend'
]

TARGET_COLUMN = 'future_return'