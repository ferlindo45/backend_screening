import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Stock configuration
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

# Feature columns
FEATURE_COLUMNS = [
    'return', 'ma5', 'ma20', 'ma50', 'volatility', 'momentum',
    'sentiment_score', 'roe', 'per', 'der', 'eps', 'dividend'
]

TARGET_COLUMN = 'future_return'