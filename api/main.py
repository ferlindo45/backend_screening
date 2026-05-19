"""
FastAPI endpoints for stock screening system - PRODUCTION READY V3.4
Semua endpoint dari versi sebelumnya + optimalisasi production
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from functools import lru_cache, wraps
import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
import json
import joblib
import os
import re
import httpx
import xml.etree.ElementTree as ET
from dateutil import parser
import logging
import platform

# Optional imports with fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from services.data_collector import DataCollector
from services.feature_engineering import FeatureEngineer
from services.sentiment_analysis import sentiment_analyzer
from services.ml_model import stock_predictor
from services.fundamental_analysis import fundamental_analyzer
from config import LQ45_STOCKS, API_HOST, API_PORT, API_DEBUG, API_KEY
from config.constants import COMPANY_NAMES, NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS
from utils.helpers import convert_to_native

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# RATE LIMITING (Optional)
# ============================================================

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False
    logger.warning("slowapi not installed, rate limiting disabled")

# Initialize FastAPI app
app = FastAPI(
    title="Stock Screening System API",
    description="API for LQ45 stock screening with ML and NLP + Fundamental Analysis",
    version="3.4.0"
)

if RATE_LIMIT_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================
# CORS & SECURITY
# ============================================================

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ============================================================
# API KEY AUTHENTICATION
# ============================================================

API_KEY = os.environ.get("API_KEY", "your-secret-api-key-here")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key"""
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# Initialize services
data_collector = DataCollector()
feature_engineer = FeatureEngineer()

# Global Semaphores for performance control
# BERT is extremely heavy on memory/CPU, limit global concurrent analyses
sentiment_semaphore = asyncio.Semaphore(1)
# Batch processing should be limited to prevent overwhelming resources/APIs
batch_semaphore = asyncio.Semaphore(3)

# Global clients
http_client = httpx.AsyncClient(timeout=15.0)

# Global variables
loaded_models = {}
models_metadata = {}
feature_names_cache = {}
sentiment_cache = {}
price_cache = {}
model_loading_complete = False

# ============================================================
# CACHE CLEANUP FUNCTIONS
# ============================================================

def cleanup_sentiment_cache():
    now = datetime.now()
    expired_keys = [
        k for k, (t, _) in sentiment_cache.items()
        if now - t > timedelta(minutes=10)
    ]
    for k in expired_keys:
        del sentiment_cache[k]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired sentiment cache entries")

def cleanup_price_cache():
    now = datetime.now()
    expired_keys = [
        k for k, (t, _) in price_cache.items()
        if now - t > timedelta(minutes=5)
    ]
    for k in expired_keys:
        del price_cache[k]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired price cache entries")

def cleanup_all_caches():
    cleanup_sentiment_cache()
    cleanup_price_cache()
    get_features_cached.cache_clear()
    logger.info("All caches cleaned")

# ============================================================
# RETRY MECHANISM
# ============================================================

def async_retry(max_retries=3, delay=1.0, backoff=2.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Final failure for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator

# ============================================================
# Rule-based and Company mappings are now in config.constants

def calculate_rule_based_sentiment(text: Optional[str]) -> tuple:
    if not text:
        return 0.0, []
    text_lower = text.lower()
    score = 0.0
    matched_keywords = []
    
    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in text_lower:
            score += weight
            matched_keywords.append((keyword, weight, 'negative'))
    
    for keyword, weight in POSITIVE_KEYWORDS.items():
        if keyword in text_lower:
            score += weight
            matched_keywords.append((keyword, weight, 'positive'))
    
    if 'laba' in text_lower and 'turun' in text_lower:
        score -= 0.25
    if 'laba' in text_lower and 'naik' in text_lower:
        score += 0.25
    if 'phk' in text_lower or 'pemutusan' in text_lower:
        score -= 0.25
    
    # Booster: Jika banyak keyword ditemukan, amplifikasi sentimennya
    pos_count = sum(1 for m in matched_keywords if m[2] == 'positive')
    neg_count = sum(1 for m in matched_keywords if m[2] == 'negative')
    
    if pos_count >= 2: score *= 1.3
    if neg_count >= 2: score *= 1.3
    
    score = max(-1, min(1, score))
    return score, matched_keywords

def combine_sentiment_scores(bert_score: float, rule_score: float, text: str = "") -> float:
    # Jika rule-based menemukan kata kunci yang kuat (abs > 0.15), berikan bobot lebih besar
    if abs(rule_score) > 0.15:
        # Jika searah (keduanya positif atau keduanya negatif), amplifikasi
        if bert_score * rule_score > 0:
            final_score = (rule_score * 0.8 + bert_score * 0.2) * 1.3
        else:
            final_score = rule_score * 0.7 + bert_score * 0.3
    else:
        # Jika bert_score menunjukkan arah yang kuat, gunakan itu
        if abs(bert_score) > 0.3:
            final_score = bert_score * 0.7 + rule_score * 0.3
        else:
            final_score = bert_score * 0.5 + rule_score * 0.5
            
    return max(-1, min(1, final_score))

# COMPANY NAMES MAPPING
# ============================================================
# Moved to config.constants

def get_company_name(stock_code: str) -> str:
    return COMPANY_NAMES.get(stock_code, stock_code.replace('.JK', ''))

# ============================================================
# CACHED PRICE FUNCTION
# ============================================================

async def get_cached_price(stock_code: str) -> dict:
    cache_key = f"price_{stock_code}"
    
    if cache_key in price_cache:
        cached_time, cached_value = price_cache[cache_key]
        if datetime.now() - cached_time < timedelta(minutes=5):
            return cached_value
    
    ticker = yf.Ticker(stock_code)
    df = await run_in_threadpool(ticker.history, period="1mo")
    
    # Handle empty data
    if df.empty:
        return {
            'current_price': 0,
            'prev_close': 0,
            'returns': [],
            'df': pd.DataFrame()
        }
    
    # Clean the data
    closes = df['Close'].dropna().values
    if len(closes) == 0:
        return {
            'current_price': 0,
            'prev_close': 0,
            'returns': [],
            'df': df
        }
    
    # Ensure no NaN/inf
    def clean_val(val):
        if val is None or np.isnan(val) or np.isinf(val):
            return 0
        return float(val)
    
    current_price = clean_val(closes[-1])
    prev_close = clean_val(closes[-2]) if len(closes) > 1 else current_price
    
    # Calculate returns without NaN
    returns = df['Close'].pct_change().dropna().values
    clean_returns = [clean_val(r) for r in returns if not np.isnan(r) and not np.isinf(r)]
    
    result = {
        'current_price': current_price,
        'prev_close': prev_close,
        'returns': clean_returns,
        'df': df
    }
    
    price_cache[cache_key] = (datetime.now(), result)
    return result

# ============================================================
# SENTIMENT ANALYSIS FUNCTIONS
# ============================================================

@async_retry(max_retries=2, delay=0.5)
async def fetch_news_with_timeout(stock_code: str, timeout_seconds: int = 30):
    return await asyncio.wait_for(
        fetch_news_with_details(stock_code),
        timeout=timeout_seconds
    )

async def analyze_single_article(item: Any) -> Optional[Dict]:
    """Helper to analyze a single news item in parallel"""
    try:
        title = item.find('title').text if item.find('title') is not None else ""
        description = item.find('description').text if item.find('description') is not None else ""
        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
        link = item.find('link').text if item.find('link') is not None else ""
        source = item.find('source').text if item.find('source') is not None else "Google News"
        
        description = re.sub(r'<[^>]+>', '', description)
        full_text = f"{title}. {description}"
        
        # Analyze sentiment
        bert_result = await run_in_threadpool(
            sentiment_analyzer.predict_sentiment_bert_cached, full_text
        )
        bert_score = bert_result['score']
        rule_score, _ = calculate_rule_based_sentiment(full_text)
        final_sentiment_score = combine_sentiment_scores(bert_score, rule_score, full_text)
        
        if final_sentiment_score >= 0.05:
            sentiment_label = "Positive"
        elif final_sentiment_score <= -0.05:
            sentiment_label = "Negative"
        else:
            sentiment_label = "Neutral"
            
        try:
            dt = parser.parse(pub_date)
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_date = pub_date
            
        return {
            'title': title,
            'date': formatted_date,
            'source': source,
            'url': link,
            'description': description[:300] + "..." if len(description) > 300 else description,
            'sentiment_score': round(final_sentiment_score, 3),
            'sentiment_label': sentiment_label,
        }
    except Exception as e:
        logger.warning(f"Error analyzing single article: {e}")
        return None

async def fetch_news_with_details(stock_code: str) -> tuple:
    try:
        company_name = get_company_name(stock_code)
        search_url = f"https://news.google.com/rss/search?q={company_name}+saham+indonesia&hl=id&gl=ID&ceid=ID:id"
        
        response = await http_client.get(search_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code != 200:
            return 0.5, 0, "Neutral", []
            
        root = ET.fromstring(response.text)
        items = root.findall('.//item')[:30]
        
        if not items:
            return 0.5, 0, "Neutral", []
            
        # Concurrency control (Global Semaphore)
        async def sem_analyze(item):
            async with sentiment_semaphore:
                return await analyze_single_article(item)
                
        # Parallel Analysis with Semaphore
        tasks = [sem_analyze(item) for item in items]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed analyses
        news_list = [r for r in results if r is not None]
        
        if news_list:
            scores = [n['sentiment_score'] for n in news_list]
            avg_score = sum(scores) / len(scores)
            normalized_score = (avg_score + 1) / 2
            normalized_score = max(0, min(1, normalized_score))
            
            if avg_score >= 0.05:
                overall_label = "Positive"
            elif avg_score <= -0.05:
                overall_label = "Negative"
            else:
                overall_label = "Neutral"
            
            return normalized_score, len(news_list), overall_label, news_list
        
        return 0.5, 0, "Neutral", []
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching news for {stock_code}")
        return 0.5, 0, "Neutral", []
    except Exception as e:
        logger.error(f"Error fetching news for {stock_code}: {e}")
        return 0.5, 0, "Neutral", []

async def fetch_news_sentiment(stock_code: str) -> tuple:
    cleanup_sentiment_cache()
    
    cache_key = f"sentiment_{stock_code}"
    if cache_key in sentiment_cache:
        cached_time, cached_value = sentiment_cache[cache_key]
        if datetime.now() - cached_time < timedelta(minutes=5):
            return cached_value
    
    try:
        score, count, label, _ = await fetch_news_with_timeout(stock_code, timeout_seconds=30)
    except asyncio.TimeoutError:
        logger.warning(f"News fetch timeout for {stock_code}, using neutral sentiment")
        score, count, label = 0.5, 0, "Neutral"
    
    result = (score, count, label)
    sentiment_cache[cache_key] = (datetime.now(), result)
    return result

def get_price_momentum(stock_code: str) -> float:
    try:
        ticker = yf.Ticker(stock_code)
        df = ticker.history(period="1mo")
        if df.empty:
            return 0
        closes = df['Close'].values
        if len(closes) >= 6:
            return (closes[-1] - closes[-6]) / closes[-6]
        elif len(closes) >= 2:
            return (closes[-1] - closes[-2]) / closes[-2]
        return 0
    except Exception:
        return 0

# ============================================================
# FEATURE EXTRACTION - FIXED dengan period 6mo
# ============================================================

@lru_cache(maxsize=100)
def get_features_cached(stock_code: str, sentiment_score: float, cache_buster: str = "") -> Optional[np.ndarray]:
    sentiment_score = round(sentiment_score, 3)
    
    try:
        logger.info(f"=== START get_features_cached for {stock_code} ===")
        logger.info(f"Extracting features for {stock_code} with sentiment={sentiment_score}")
        
        # FIX: Coba dengan periode yang berbeda
        ticker = yf.Ticker(stock_code)
        
        # Coba dengan period "1y" dulu, lalu fallback ke "6mo", lalu "3mo"
        periods_to_try = ["1y", "6mo", "3mo", "1mo"]
        df = None
        used_period = None
        
        for period in periods_to_try:
            try:
                logger.info(f"Trying period={period} for {stock_code}")
                df = ticker.history(period=period)
                if df is not None and not df.empty and len(df) >= 30:
                    logger.info(f"✓ Successfully got {len(df)} rows with period={period}")
                    used_period = period
                    break
                else:
                    logger.warning(f"Period {period} returned {len(df) if df is not None else 0} rows")
            except Exception as e:
                logger.warning(f"Failed with period={period}: {e}")
                continue
        
        if df is None or df.empty:
            logger.error(f"Step 1 FAILED: No data for {stock_code} after trying all periods")
            return None
        
        logger.info(f"Step 1 OK: Got {len(df)} rows of data using period={used_period}")
        
        # Check minimum data requirement
        min_required = 50
        if len(df) < min_required:
            logger.warning(f"Only {len(df)} rows available, need at least {min_required}")
            return None
        
        # Reset index
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        logger.info(f"Step 2 OK: Date column processed")
        
        # Get fundamental data
        try:
            fundamental = data_collector.get_fundamental_data(stock_code)
            logger.info(f"Step 3 OK: Got fundamental data: ROE={fundamental.get('roe', 'N/A')}")
        except Exception as e:
            logger.error(f"Step 3 FAILED: {e}")
            return None
        
        # Create sentiment dataframe
        try:
            dates = pd.to_datetime(df['Date'])
            sentiment_df = pd.DataFrame({
                'date': dates,
                'sentiment_score': sentiment_score,
                'sentiment_positive': max(0, sentiment_score),
                'sentiment_neutral': 1 - abs(sentiment_score),
                'sentiment_negative': max(0, -sentiment_score)
            })
            logger.info(f"Step 4 OK: Sentiment DF created with shape={sentiment_df.shape}")
        except Exception as e:
            logger.error(f"Step 4 FAILED: {e}")
            return None
        
        # Create complete dataset
        try:
            df_complete = feature_engineer.create_complete_dataset(df, fundamental, sentiment_df)
            if df_complete.empty:
                logger.error(f"Step 5 FAILED: create_complete_dataset returned empty")
                logger.info(f"  Input df shape: {df.shape}")
                logger.info(f"  Fundamental keys: {fundamental.keys()}")
                return None
            logger.info(f"Step 5 OK: df_complete shape={df_complete.shape}")
        except Exception as e:
            logger.error(f"Step 5 FAILED: {e}", exc_info=True)
            return None
        
        # Prepare features
        try:
            X, _, feature_names = feature_engineer.prepare_features_for_model(df_complete)
            if len(X) == 0:
                logger.error(f"Step 6 FAILED: No features after prepare_features_for_model")
                logger.info(f"  df_complete shape: {df_complete.shape}")
                logger.info(f"  Columns: {df_complete.columns.tolist()}")
                return None
            logger.info(f"Step 6 OK: X shape={X.shape}, features={feature_names[:3]}...")
        except Exception as e:
            logger.error(f"Step 6 FAILED: {e}", exc_info=True)
            return None
        
        # Cache feature names
        global feature_names_cache
        if stock_code not in feature_names_cache:
            feature_names_cache[stock_code] = feature_names
        
        result = X[-1:].reshape(1, -1)
        logger.info(f"Step 7 OK: Final features shape={result.shape}")
        logger.info(f"=== END get_features_cached SUCCESS for {stock_code} ===")
        
        return result
        
    except Exception as e:
        logger.error(f"Feature extraction error for {stock_code}: {str(e)}", exc_info=True)
        return None
    

async def extract_features_for_prediction(stock_code: str, sentiment_score: float) -> np.ndarray:
    cache_buster = datetime.now().strftime("%Y%m%d%H")
    features = await run_in_threadpool(
        get_features_cached, stock_code, sentiment_score, cache_buster
    )
    
    if features is None:
        raise ValueError(f"Failed to extract features for {stock_code}")
    
    return features

# ============================================================
# BACKGROUND MODEL LOADING
# ============================================================

async def load_models_background():
    global loaded_models, models_metadata, model_loading_complete
    
    models_dir = "models/saved_models"
    if not os.path.exists(models_dir):
        logger.warning(f"Directory {models_dir} not found")
        model_loading_complete = True
        return
    
    logger.info("="*50)
    logger.info("LOADING TRAINED MODELS (BACKGROUND)")
    logger.info("="*50)
    
    model_files = [f for f in os.listdir(models_dir) if f.startswith("random_forest_") and f.endswith(".pkl")]
    
    for model_file in model_files:
        stock_code = model_file.replace("random_forest_", "").replace(".pkl", "")
        model_path = os.path.join(models_dir, model_file)
        scaler_path = os.path.join(models_dir, f"scaler_{stock_code}.pkl")
        
        try:
            model = await run_in_threadpool(joblib.load, model_path)
            entry = {'random_forest': model}
            
            if os.path.exists(scaler_path):
                scaler = await run_in_threadpool(joblib.load, scaler_path)
                entry['scaler'] = scaler
                logger.info(f"✓ Loaded model and scaler for {stock_code}")
            else:
                logger.info(f"✓ Loaded model for {stock_code} (no scaler found)")
                
            loaded_models[stock_code] = entry
        except Exception as e:
            logger.error(f"✗ Failed to load {stock_code}: {e}")
    
    logger.info(f"✓ Total {len(loaded_models)} stocks loaded")
    logger.info("="*50)

# Global variables
loaded_models = {}
sentiment_cache = {}
# Institutional Cache for Pre-fetched data
lq45_data_cache = {} 
industry_benchmarks_calculated = False

# ============================================================
# INSTITUTIONAL SERVICES (MAXIMAL UPGRADE)
# ============================================================

class TelegramService:
    """Placeholder for Telegram Alerting Service"""
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

    async def send_alert(self, message: str):
        if not self.enabled:
            logger.info(f"Telegram Alert (Simulated): {message}")
            return
        # Real implementation would use httpx to call Telegram API
        pass

telegram_service = TelegramService()

@app.on_event("startup")
async def startup_event():
    """Perform maximal startup optimizations"""
    logger.info("=== PERFORMING MAXIMAL STARTUP OPTIMIZATIONS ===")
    
    # 1. Background model loading
    asyncio.create_task(load_models_background())
    
    # 2. Batch Pre-fetching LQ45 (OHLCV)
    # yf.download is much faster for bulk data
    try:
        logger.info(f"Pre-fetching data for {len(LQ45_STOCKS)} stocks...")
        bulk_data = await run_in_threadpool(
            yf.download, 
            tickers=LQ45_STOCKS, 
            period="2y", 
            interval="1d", 
            group_by='ticker'
        )
        
        for stock in LQ45_STOCKS:
            if stock in bulk_data:
                lq45_data_cache[stock] = bulk_data[stock]
        
        logger.info(f"✓ Pre-fetched OHLCV data for {len(lq45_data_cache)} stocks")
    except Exception as e:
        logger.error(f"Failed bulk pre-fetch: {e}")

    # 3. Industry Benchmarking (Cold Start)
    asyncio.create_task(calculate_initial_benchmarks())

async def calculate_initial_benchmarks():
    """Calculate industry averages for the whole LQ45"""
    global industry_benchmarks_calculated
    logger.info("Calculating initial industry benchmarks...")
    
    all_metrics = []
    # Limit to first 10 for startup speed, full background refresh later
    sample_stocks = LQ45_STOCKS[:15] 
    
    for stock in sample_stocks:
        try:
            # Get basic metrics without full valuation for speed
            ticker = yf.Ticker(stock)
            info = ticker.info
            if info:
                metrics = fundamental_analyzer._get_basic_metrics(info, pd.DataFrame())
                metrics['company_type'], _ = fundamental_analyzer.classify_company(info)
                all_metrics.append(metrics)
        except:
            continue
            
    fundamental_analyzer.update_industry_averages(all_metrics)
    industry_benchmarks_calculated = True
    logger.info(f"✓ Industry benchmarks calculated for {len(fundamental_analyzer.industry_averages)} sectors")
    logger.info("API started, models loading in background")

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()
    logger.info("API shutdown complete")

# ============================================================
# PYDANTIC MODELS
# ============================================================

class StockRequest(BaseModel):
    stock_codes: List[str] = Field(default=LQ45_STOCKS, description="List of stock codes")

class TrainRequest(BaseModel):
    stock_code: str = Field(..., description="Stock code to train model on")
    include_sentiment: bool = Field(default=True, description="Include sentiment features")

class PredictRequest(BaseModel):
    stock_code: str = Field(..., description="Stock code for prediction")

class SentimentRequest(BaseModel):
    text: str = Field(..., description="Text to analyze sentiment")
    
class StockDataResponse(BaseModel):
    stock_code: str
    data: List[Dict]
    total_records: int

class TrainResponse(BaseModel):
    stock_code: str
    evaluation: Dict
    feature_importance: Dict
    train_size: int
    test_size: int
    message: str

class PredictResponse(BaseModel):
    stock_code: str
    predictions: Dict[str, float]
    sentiment_score: float
    sentiment_label: str
    news_analyzed: int
    final_score: float
    recommendation: str

class SentimentResponse(BaseModel):
    text: str
    sentiment: Dict[str, float]
    sentiment_score: float

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    available_models: List[str]
    models_loaded: bool
    cache_size: int
    system_stats: Dict

class NewsItem(BaseModel):
    title: str
    date: str
    source: str
    url: str
    sentiment_score: float
    sentiment_label: str

class StockSentimentResponse(BaseModel):
    stock_code: str
    company_name: str
    overall_sentiment_score: float
    overall_sentiment_label: str
    news_analyzed: int
    news_items: List[NewsItem]
    last_updated: str

class AnalysisSection(BaseModel):
    score: float
    status: str
    details: Dict[str, Any]
    rationale: str

class FullAnalysisResponse(BaseModel):
    stock_code: str
    company_name: str
    current_price: float
    recommendation: str
    final_score: float
    fundamental: AnalysisSection
    technical: AnalysisSection
    sentiment: AnalysisSection
    summary_rationale: str
    last_updated: str

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_final_score(fund_score: Optional[float], tech_score: Optional[float], sent_score: Optional[float]) -> float:
    # Handle None values
    fund_score = fund_score if fund_score is not None else 50.0
    tech_score = tech_score if tech_score is not None else 50.0
    sent_score = sent_score if sent_score is not None else 0.5
    
    # Normalize scores if they are in 0-100 range
    f = fund_score / 100 if fund_score > 1 else fund_score
    t = tech_score / 100 if tech_score > 1 else tech_score
    s = sent_score # Sentiment is already 0-1
    
    # Formula: 50% Fundamental, 30% Teknikal, 20% Sentimen
    final = (0.5 * f) + (0.3 * t) + (0.2 * s)
    
    return round(float(final), 3)

def get_recommendation(final_score: float) -> str:
    """Professional recommendation labels"""
    if final_score >= 0.75:
        return "STRONG BUY"
    elif final_score >= 0.60:
        return "ACCUMULATE"
    elif final_score >= 0.45:
        return "HOLD"
    elif final_score >= 0.30:
        return "REDUCE"
    else:
        return "SELL"

async def get_robust_price(stock_code: str) -> float:
    """Robust price fetcher with multiple fallbacks"""
    try:
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        
        # Fallback chain
        price = info.get('currentPrice') or \
                info.get('regularMarketPrice') or \
                info.get('previousClose')
                
        if not price or price == 0:
            df = await run_in_threadpool(ticker.history, period="5d")
            if not df.empty:
                price = df['Close'].iloc[-1]
                
        return float(price) if price else 0.0
    except:
        return 0.0

def calculate_risk_metrics(df: pd.DataFrame) -> Dict:
    """Calculate risk metrics for professional audit"""
    if df.empty or len(df) < 20:
        return {"volatility": 0, "max_drawdown": 0, "risk_level": "Unknown"}
    
    # 1. Volatility (Annualized)
    returns = df['Close'].pct_change().dropna()
    vol = returns.std() * np.sqrt(252) * 100
    
    # 2. Max Drawdown
    roll_max = df['Close'].cummax()
    drawdown = (df['Close'] - roll_max) / roll_max
    max_drawdown = drawdown.min() * 100
    
    risk_level = "Low"
    if vol > 40: risk_level = "High"
    elif vol > 25: risk_level = "Moderate"
    
    return {
        "volatility_annual": round(float(vol), 2),
        "max_drawdown_1y": round(float(max_drawdown), 2),
        "risk_level": risk_level
    }

# ============================================================
# MONITORING ENDPOINT
# ============================================================

@app.get("/metrics")
async def get_metrics():
    result = {
        "models_loaded": len(loaded_models),
        "sentiment_cache_size": len(sentiment_cache),
        "price_cache_size": len(price_cache),
        "feature_cache_size": get_features_cached.cache_info().currsize if hasattr(get_features_cached, 'cache_info') else 0,
        "python_version": platform.python_version(),
        "platform": platform.platform()
    }
    
    if PSUTIL_AVAILABLE:
        result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        result["memory_percent"] = psutil.virtual_memory().percent
        result["memory_used_mb"] = psutil.virtual_memory().used / 1024 / 1024
    else:
        result["cpu_percent"] = "N/A (install psutil)"
        result["memory_percent"] = "N/A (install psutil)"
        result["memory_used_mb"] = "N/A (install psutil)"
    
    return result

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/", response_model=HealthResponse)
async def health_check():
    cache_size = get_features_cached.cache_info().currsize if hasattr(get_features_cached, 'cache_info') else 0
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        available_models=list(loaded_models.keys())[:10],
        models_loaded=model_loading_complete,
        cache_size=cache_size,
        system_stats={
            "models_total": len(loaded_models),
            "sentiment_cache": len(sentiment_cache),
            "price_cache": len(price_cache)
        }
    )

@app.get("/get-stock-data", response_model=List[StockDataResponse])
async def get_stock_data(stock_codes: Optional[str] = None):
    if stock_codes:
        codes = stock_codes.split(',')
    else:
        codes = LQ45_STOCKS[:5]
    
    results = []
    for code in codes:
        df = data_collector.load_saved_data(code)
        if df.empty:
            df = data_collector.download_stock_data(code)
        
        if not df.empty:
            data_dict = df.tail(100).to_dict(orient='records')
            for record in data_dict:
                for key, value in record.items():
                    if hasattr(value, 'item'):
                        record[key] = value.item()
            
            results.append(StockDataResponse(
                stock_code=code,
                data=data_dict,
                total_records=len(df)
            ))
        else:
            results.append(StockDataResponse(
                stock_code=code,
                data=[],
                total_records=0
            ))
    
    return results

@app.post("/train-model", response_model=TrainResponse)
async def train_model(request: TrainRequest, background_tasks: BackgroundTasks):
    try:
        print(f"Collecting data for {request.stock_code}...")
        df_raw = data_collector.download_stock_data(request.stock_code)
        
        if df_raw.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {request.stock_code}")
        
        fundamental_data = data_collector.get_fundamental_data(request.stock_code)
        
        sentiment_df = None
        if request.include_sentiment:
            dates = pd.to_datetime(df_raw['Date']).dt.tz_localize(None)
            sentiment_df = pd.DataFrame({
                'date': dates,
                'sentiment_score': 0.5,
                'sentiment_positive': 0.4,
                'sentiment_neutral': 0.4,
                'sentiment_negative': 0.2
            })
        
        df_complete = feature_engineer.create_complete_dataset(df_raw, fundamental_data, sentiment_df)
        
        if df_complete.empty:
            raise HTTPException(status_code=400, detail="No valid data after feature engineering")
        
        X, y, feature_names = feature_engineer.prepare_features_for_model(df_complete)
        
        print(f"Features shape: {X.shape}")
        print(f"Features used: {feature_names}")
        
        training_results = stock_predictor.train_and_evaluate(X, y)
        background_tasks.add_task(stock_predictor.save_models, request.stock_code)
        
        return TrainResponse(
            stock_code=request.stock_code,
            evaluation=training_results['evaluation'],
            feature_importance={
                name: importance.tolist() if hasattr(importance, 'tolist') else importance
                for name, importance in training_results['feature_importance'].items()
            },
            train_size=training_results['train_size'],
            test_size=training_results['test_size'],
            message="Model training completed successfully"
        )
        
    except Exception as e:
        print(f"Error in training: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict", response_model=PredictResponse)
async def predict(request: Request, pred_req: PredictRequest, api_key: str = Depends(verify_api_key)):
    stock_code = pred_req.stock_code
    
    try:
        if stock_code not in loaded_models:
            raise HTTPException(status_code=404, detail="Stock not found")
        
        model = loaded_models[stock_code].get('random_forest')
        scaler = loaded_models[stock_code].get('scaler')
        
        if not model:
            raise HTTPException(status_code=400, detail="Model not available")
        
        sent_score, news_count, sent_label, _ = await fetch_news_with_timeout(stock_code)
        
        features = await extract_features_for_prediction(stock_code, sent_score)
        
        # Apply scaling if available
        if scaler:
            features_scaled = scaler.transform(features)
            prediction = await run_in_threadpool(model.predict, features_scaled)
        else:
            prediction = await run_in_threadpool(model.predict, features)
            
        predicted_return = float(prediction[0])
        
        # Get fundamental score
        fund_data = await run_in_threadpool(fundamental_analyzer.get_complete_fundamental_data, stock_code)
        fund_score = float(fund_data.get('fundamental_recommendation', {}).get('score', 50))
        
        # Tech score from prediction
        tech_score = 50.0
        if predicted_return > 0.02: tech_score = 80.0
        elif predicted_return > 0: tech_score = 65.0
        elif predicted_return < -0.02: tech_score = 20.0
        
        final_score = calculate_final_score(fund_score, tech_score, sent_score)
        recommendation = get_recommendation(final_score)
        
        return PredictResponse(
            stock_code=stock_code,
            predictions={'ensemble': predicted_return},
            sentiment_score=sent_score,
            sentiment_label=sent_label,
            news_analyzed=news_count,
            final_score=final_score,
            recommendation=recommendation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Predict error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(request: Request, sent_req: SentimentRequest):
    try:
        result = await run_in_threadpool(
            sentiment_analyzer.predict_sentiment_bert, sent_req.text
        )
        return SentimentResponse(
            text=sent_req.text,
            sentiment={
                'positive': result['positive'],
                'neutral': result['neutral'],
                'negative': result['negative']
            },
            sentiment_score=result['score']
        )
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_single_stock(code: str) -> dict:
    try:
        if code not in loaded_models:
            return {'stock_code': code, 'error': 'Model not found'}
        
        sent_score, news_count, sent_label, _ = await fetch_news_with_timeout(code)
        
        # Check if fundamental data is dummy
        fund_data = await run_in_threadpool(fundamental_analyzer.get_complete_fundamental_data, code)
        is_dummy = fund_data.get('is_dummy', False)
        fund_score = float(fund_data.get('fundamental_recommendation', {}).get('score', 50))
        
        model = loaded_models[code].get('random_forest')
        scaler = loaded_models[code].get('scaler')
        
        predicted_return = 0.0
        tech_score = 50.0
        
        if model:
            try:
                features = await extract_features_for_prediction(code, sent_score)
                if features is not None:
                    # Apply scaling if available
                    if scaler:
                        features_scaled = scaler.transform(features)
                        prediction = await run_in_threadpool(model.predict, features_scaled)
                    else:
                        prediction = await run_in_threadpool(model.predict, features)
                        
                    predicted_return = float(prediction[0])
                    
                    if predicted_return > 0.02: tech_score = 80.0
                    elif predicted_return > 0: tech_score = 65.0
                    elif predicted_return < -0.02: tech_score = 20.0
                else:
                    logger.warning(f"Feature extraction failed for {code}")
            except Exception as e:
                logger.warning(f"Prediction failed for {code}: {e}")
        
        final_score = calculate_final_score(fund_score, tech_score, sent_score)
        recommendation = get_recommendation(final_score)
        
        return {
            'stock_code': code,
            'predicted_return': round(predicted_return, 4),
            'sentiment_score': sent_score,
            'sentiment_label': sent_label,
            'news_analyzed': news_count,
            'final_score': final_score,
            'recommendation': recommendation,
            'is_dummy_data': is_dummy
        }
    except Exception as e:
        logger.warning(f"Error processing {code}: {e}")
        return {'stock_code': code, 'error': str(e)}

@app.get("/batch-predict")
async def batch_predict(request: Request, stock_codes: Optional[str] = None):
    try:
        if stock_codes:
            codes = stock_codes.split(',')
        else:
            codes = list(loaded_models.keys())
        
        logger.info(f"Batch predict: processing {len(codes)} stocks in parallel")
        
        async def sem_process(code):
            async with batch_semaphore:
                return await process_single_stock(code)
                
        tasks = [sem_process(code) for code in codes]
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if 'error' not in r]
        valid_results.sort(key=lambda x: x.get('final_score', 0), reverse=True)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_stocks_analyzed': len(valid_results),
            'results': valid_results
        }
        
    except Exception as e:
        logger.error(f"Batch predict error: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'total_stocks_analyzed': 0,
            'results': [],
            'error': str(e)
        }

@app.get("/stock-news/{stock_code}", response_model=StockSentimentResponse)
async def get_stock_news(stock_code: str):
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        overall_score, news_count, overall_label, news_items = await fetch_news_with_details(stock_code)
        company_name = get_company_name(stock_code)
        
        return StockSentimentResponse(
            stock_code=stock_code,
            company_name=company_name,
            overall_sentiment_score=round(overall_score, 3),
            overall_sentiment_label=overall_label,
            news_analyzed=news_count,
            news_items=[NewsItem(**item) for item in news_items],
            last_updated=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stock-sentiment/{stock_code}")
async def get_stock_sentiment(stock_code: str):
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        sentiment_score, news_count, sentiment_label = await fetch_news_sentiment(stock_code)
        company_name = get_company_name(stock_code)
        
        return {
            'stock_code': stock_code,
            'company_name': company_name,
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'news_analyzed': news_count,
            'last_updated': datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stock-info/{stock_code}")
async def get_stock_info(stock_code: str):
    try:
        # Add .JK if not present
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        # Helper function to clean float values
        def clean_float(value, default=0):
            """Convert NaN, None, inf to default value"""
            if value is None:
                return default
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    return default
            return float(value)
        
        # Get price data
        ticker = yf.Ticker(stock_code)
        df = ticker.history(period="1mo")
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {stock_code}")
        
        # Clean price data
        closes = df['Close'].dropna().values
        if len(closes) == 0:
            raise HTTPException(status_code=404, detail=f"No price data for {stock_code}")
        
        latest_close = clean_float(closes[-1])
        prev_close = clean_float(closes[-2]) if len(closes) > 1 else latest_close
        
        # Calculate daily change
        daily_change = 0.0
        if prev_close != 0:
            daily_change = ((latest_close - prev_close) / prev_close * 100)
        daily_change = clean_float(daily_change)
        
        # Calculate volatility
        returns = df['Close'].pct_change().dropna()
        volatility = 0.0
        if len(returns) > 0:
            # Clean returns data
            clean_returns = [clean_float(r) for r in returns.values if not np.isnan(r) and not np.isinf(r)]
            if len(clean_returns) > 0:
                volatility = np.std(clean_returns) * (252 ** 0.5) * 100
        volatility = clean_float(volatility)
        
        # Get fundamental data
        fundamental = data_collector.get_fundamental_data(stock_code)
        cleaned_fundamental = {
            'roe': clean_float(fundamental.get('roe', 0)),
            'per': clean_float(fundamental.get('per', 0)),
            'der': clean_float(fundamental.get('der', 0)),
            'eps': clean_float(fundamental.get('eps', 0)),
            'dividend': clean_float(fundamental.get('dividend', 0))
        }
        
        # Get news sentiment
        try:
            overall_score, news_count, overall_label, news_items = await fetch_news_with_details(stock_code)
            overall_score = clean_float(overall_score, 0.5)
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
            overall_score = 0.5
            news_count = 0
            overall_label = "Neutral"
            news_items = []
        
        # Prepare response
        response = {
            'stock_code': stock_code,
            'company_name': get_company_name(stock_code),
            'current_price': round(latest_close, 2),
            'daily_change_percent': round(daily_change, 2),
            'volatility_annual': round(volatility, 2),
            'sentiment_score': round(overall_score, 3),
            'sentiment_label': overall_label if overall_label else "Neutral",
            'news_analyzed': news_count if news_count else 0,
            'latest_news': [
                {
                    'title': str(item.get('title', '')),
                    'date': str(item.get('date', '')),
                    'source': str(item.get('source', '')),
                    'sentiment': str(item.get('sentiment_label', 'Neutral'))
                } for item in (news_items[:3] if news_items else [])
            ],
            'fundamental_metrics': cleaned_fundamental,
            'last_updated': datetime.now().isoformat()
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stock info error for {stock_code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fundamental-analysis/{stock_code}")
async def get_fundamental_analysis(stock_code: str):
    """Get comprehensive fundamental analysis"""
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        result = fundamental_analyzer.get_complete_fundamental_data(stock_code)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        # Convert all numpy types using helper
        safe_result = convert_to_native(result)
        
        # Return dict directly
        return {
            'stock_code': str(stock_code),
            'current_price': float(safe_result.get('current_price', 0)),
            'eps_ttm': float(safe_result.get('eps_ttm', 0)),
            'eps_forward': float(safe_result.get('eps_forward', 0)),
            'bvps': float(safe_result.get('bvps', 0)),
            'per_ttm': float(safe_result.get('per_ttm', 0)),
            'per_forward': float(safe_result.get('per_forward', 0)),
            'pbv': float(safe_result.get('pbv', 0)),
            'der': float(safe_result.get('der', 0)),
            'roe': float(safe_result.get('roe', 0)),
            'roa': float(safe_result.get('roa', 0)),
            'net_profit_margin': float(safe_result.get('net_profit_margin', 0)),
            'operating_margin': float(safe_result.get('operating_margin', 0)),
            'fair_value': float(safe_result.get('fair_value', 0)),
            'fair_value_dcf': float(safe_result.get('fair_value_dcf', 0)) if safe_result.get('fair_value_dcf') else 0,
            'fair_value_per': float(safe_result.get('fair_value_per', 0)) if safe_result.get('fair_value_per') else 0,
            'fair_value_pbv': float(safe_result.get('fair_value_pbv', 0)) if safe_result.get('fair_value_pbv') else 0,
            'upside_potential': float(safe_result.get('upside_potential', 0)),
            'margin_of_safety': safe_result.get('margin_of_safety', {}),
            'fundamental_recommendation': safe_result.get('fundamental_recommendation', {}),
            'sector': str(safe_result.get('sector', 'Unknown')),
            'last_updated': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fundamental analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fair-value/{stock_code}")
async def get_fair_value(stock_code: str):
    """Get Fair Value and Margin of Safety only (quick valuation)"""
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        result = fundamental_analyzer.get_complete_fundamental_data(stock_code)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        # Convert all numpy types using helper
        safe_result = convert_to_native(result)
        
        # Extract values safely
        margin_of_safety = safe_result.get('margin_of_safety', {})
        if not isinstance(margin_of_safety, dict):
            margin_of_safety = {}
        
        valuation_weights = safe_result.get('valuation_method_weights', {})
        if not isinstance(valuation_weights, dict):
            valuation_weights = {}
        
        return {
            'stock_code': str(stock_code),
            'current_price': float(safe_result.get('current_price', 0)),
            'fair_value': float(safe_result.get('fair_value', 0)),
            'fair_value_dcf': float(safe_result.get('fair_value_dcf', 0)) if safe_result.get('fair_value_dcf') else 0,
            'fair_value_per': float(safe_result.get('fair_value_per', 0)) if safe_result.get('fair_value_per') else 0,
            'fair_value_pbv': float(safe_result.get('fair_value_pbv', 0)) if safe_result.get('fair_value_pbv') else 0,
            'fair_value_ddm': float(safe_result.get('fair_value_ddm', 0)) if safe_result.get('fair_value_ddm') else 0,
            'fair_value_excess': float(safe_result.get('fair_value_excess', 0)) if safe_result.get('fair_value_excess') else 0,
            'upside_potential': float(safe_result.get('upside_potential', 0)),
            'margin_of_safety': {
                'percentage': float(margin_of_safety.get('percentage', 0)),
                'level': str(margin_of_safety.get('level', 'N/A')),
                'action': str(margin_of_safety.get('action', 'N/A')),
                'description': str(margin_of_safety.get('description', ''))
            },
            'valuation_method_weights': {
                'dcf': int(valuation_weights.get('dcf', 0)),
                'per': int(valuation_weights.get('per', 0)),
                'pbv': int(valuation_weights.get('pbv', 0)),
                'ddm': int(valuation_weights.get('ddm', 0)) if valuation_weights.get('ddm') else 0,
                'excess': int(valuation_weights.get('excess', 0)) if valuation_weights.get('excess') else 0
            },
            'dcf_valid': bool(safe_result.get('dcf_valid', False)),
            'ddm_valid': bool(safe_result.get('ddm_valid', False)),
            'excess_valid': bool(safe_result.get('excess_valid', False)),
            'last_updated': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fair value error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/admin/clear-cache")
async def admin_clear_cache():
    cleanup_all_caches()
    return {"status": "success", "message": "All caches cleared"}

# ============================================================
# DEBUG ENDPOINT (untuk troubleshooting)
# ============================================================

@app.get("/debug/features/{stock_code}")
async def debug_features(stock_code: str):
    """Debug endpoint untuk cek feature extraction"""
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        sentiment_score = 0.5
        result = {"stock_code": stock_code, "steps": {}}
        
        ticker = yf.Ticker(stock_code)
        df = ticker.history(period="6mo")
        
        if df.empty:
            result["steps"]["1_download"] = {"status": "FAILED", "error": "No data"}
            return result
        result["steps"]["1_download"] = {"status": "OK", "rows": len(df)}
        
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        result["steps"]["2_reset_index"] = {"status": "OK"}
        
        fundamental = data_collector.get_fundamental_data(stock_code)
        result["steps"]["3_fundamental"] = {"status": "OK", "roe": fundamental.get('roe')}
        
        dates = pd.to_datetime(df['Date'])
        sentiment_df = pd.DataFrame({
            'date': dates,
            'sentiment_score': sentiment_score,
            'sentiment_positive': max(0, sentiment_score),
            'sentiment_neutral': 1 - abs(sentiment_score),
            'sentiment_negative': max(0, -sentiment_score)
        })
        result["steps"]["4_sentiment_df"] = {"status": "OK", "shape": sentiment_df.shape}
        
        try:
            df_complete = feature_engineer.create_complete_dataset(df, fundamental, sentiment_df)
            if df_complete.empty:
                result["steps"]["5_complete_dataset"] = {"status": "FAILED", "error": "Empty dataframe"}
                return result
            result["steps"]["5_complete_dataset"] = {"status": "OK", "shape": df_complete.shape}
        except Exception as e:
            result["steps"]["5_complete_dataset"] = {"status": "FAILED", "error": str(e)}
            return result
        
        try:
            X, y, feature_names = feature_engineer.prepare_features_for_model(df_complete)
            if len(X) == 0:
                result["steps"]["6_prepare_features"] = {"status": "FAILED", "error": "No features"}
                return result
            result["steps"]["6_prepare_features"] = {"status": "OK", "X_shape": X.shape, "features_count": len(feature_names)}
        except Exception as e:
            result["steps"]["6_prepare_features"] = {"status": "FAILED", "error": str(e)}
            return result
        
        result["success"] = True
        result["latest_features_shape"] = X[-1:].shape
        
        return result
        
    except Exception as e:
        return {"error": str(e), "stock_code": stock_code}

# ============================================================
# RUN APP
# ============================================================

@app.get("/analyze/{stock_code}", response_model=FullAnalysisResponse)
async def analyze_stock_full(stock_code: str):
    """
    Professional Comprehensive Analysis:
    - 50% Fundamental
    - 30% Technical
    - 20% Sentiment
    """
    try:
        if not stock_code.endswith('.JK'):
            stock_code = f"{stock_code}.JK"
        
        company_name = get_company_name(stock_code)
        
        # 0. PRICE & HISTORY
        current_price = await get_robust_price(stock_code)
        # 1. Technical Analysis
        df_hist = lq45_data_cache.get(stock_code)
        if df_hist is None or df_hist.empty:
            ticker = yf.Ticker(stock_code)
            df_hist = await run_in_threadpool(ticker.history, period="2y")
        
        if current_price == 0 and not df_hist.empty:
            current_price = float(df_hist['Close'].iloc[-1])

        # 1. FUNDAMENTAL ANALYSIS
        fund_data = await run_in_threadpool(fundamental_analyzer.get_complete_fundamental_data, stock_code)
        if 'error' in fund_data:
            raise HTTPException(status_code=404, detail=fund_data['error'])
        
        fund_safe = convert_to_native(fund_data)
        fund_score = float(fund_safe.get('fundamental_recommendation', {}).get('score', 50))
        
        # Rationale Fundamental
        fund_rationale = f"Saham {company_name} memiliki valuasi {fund_safe.get('valuation_status')} "
        fund_rationale += f"dengan Upside Potential {fund_safe.get('upside_potential')}% (Fair Value: Rp{fund_safe.get('fair_value')}). "
        
        bench = fund_safe.get('industry_benchmarking', {})
        if bench.get('status') == 'BETTER':
            fund_rationale += f" Performa di atas rata-rata industri {fund_safe.get('company_type')}. "
        elif bench.get('status') == 'MIXED':
            fund_rationale += f" Performa campuran dibandingkan rata-rata industri {fund_safe.get('company_type')}. "
            
        fund_rationale += f"Profitabilitas: { 'Baik' if fund_safe.get('roe',0) > 12 else 'Cukup' } (ROE: {fund_safe.get('roe')}%)."

        fund_section = AnalysisSection(
            score=fund_score,
            status=str(fund_safe.get('fundamental_recommendation', {}).get('label', 'Neutral')),
            details={
                'fair_value': fund_safe.get('fair_value'),
                'upside': fund_safe.get('upside_potential'),
                'per': fund_safe.get('per_ttm'),
                'pbv': fund_safe.get('pbv'),
                'der': fund_safe.get('der'),
                'roe': fund_safe.get('roe'),
                'roa': fund_safe.get('roa'),
                'op_margin': fund_safe.get('operating_margin'),
                'industry_benchmarking': bench
            },
            rationale=fund_rationale
        )

        # 2. SENTIMENT ANALYSIS
        sent_score, news_count, sent_label, news_items = await fetch_news_with_timeout(stock_code)
        
        sent_section = AnalysisSection(
            score=round(float(sent_score * 100), 2),
            status=str(sent_label),
            details={
                'news_count': news_count,
                'top_headlines': [n['title'] for n in news_items[:3]]
            },
            rationale=f"Sentimen pasar {sent_label} berdasarkan {news_count} berita. Skor normalisasi: {round(sent_score, 2)}."
        )

        # 3. TECHNICAL ANALYSIS
        tech_score = 50.0
        tech_details = {}
        tech_rationale = "Data teknikal tidak tersedia."
        
        if not df_hist.empty:
            df_tech = feature_engineer.calculate_technical_features(df_hist)
            
            # Ensure we get the latest row with valid indicators
            valid_rows = df_tech.dropna(subset=['ma20', 'rsi'])
            if valid_rows.empty:
                latest = df_tech.iloc[-1]
            else:
                latest = valid_rows.iloc[-1]
            
            # Trend Analysis
            ma20 = float(latest['ma20']) if not np.isnan(latest['ma20']) else None
            ma50 = float(latest['ma50']) if not np.isnan(latest['ma50']) else None
            ma200 = float(latest['ma200']) if not np.isnan(latest['ma200']) else None
            rsi = float(latest['rsi']) if not np.isnan(latest['rsi']) else 50.0
            macd = float(latest['macd_hist']) if not np.isnan(latest['macd_hist']) else 0.0
            
            trend = "Bullish" if current_price > ma20 and ma20 > ma50 else "Bearish"
            cross = "Golden Cross" if latest['golden_cross'] == 1 else "Normal"
            
            # Risk Metrics
            risk = calculate_risk_metrics(df_hist)
            
            # Tech Score calculation (simple)
            t_score = 50
            if trend == "Bullish": t_score += 20
            if rsi < 30: t_score += 15 # Oversold
            if rsi > 70: t_score -= 15 # Overbought
            if macd > 0: t_score += 10
            
            tech_score = float(max(0, min(100, t_score)))
            
            tech_details = {
                'rsi': round(rsi, 2),
                'macd': "Bullish" if macd > 0 else "Bearish",
                'ma20': round(ma20, 2) if not np.isnan(ma20) else None,
                'ma50': round(ma50, 2) if not np.isnan(ma50) else None,
                'ma200': round(ma200, 2) if not np.isnan(ma200) else None,
                'bb_upper': round(float(latest['bb_upper']), 2) if not np.isnan(latest['bb_upper']) else None,
                'bb_lower': round(float(latest['bb_lower']), 2) if not np.isnan(latest['bb_lower']) else None,
                'support': round(float(latest['support']), 2) if not np.isnan(latest['support']) else None,
                'resistance': round(float(latest['resistance']), 2) if not np.isnan(latest['resistance']) else None,
                'trend': trend,
                'risk': risk
            }
            
            tech_rationale = f"Tren saat ini {trend} ({cross}). RSI berada di level {round(rsi, 2)} "
            tech_rationale += f"yang menunjukkan kondisi { 'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral' }. "
            if current_price > latest['resistance']: tech_rationale += "Harga menembus Resistance! "
            tech_rationale += f"Risk level: {risk['risk_level']} (Vol: {risk['volatility_annual']}%)."

        tech_section = AnalysisSection(
            score=tech_score,
            status="Positive" if tech_score > 60 else "Negative" if tech_score < 40 else "Neutral",
            details=tech_details,
            rationale=tech_rationale
        )

        # 4. FINAL AGGREGATION (50/30/20)
        final_score = calculate_final_score(fund_score, tech_score, sent_score)
        recommendation = get_recommendation(final_score)
        
        summary = f"Rekomendasi {recommendation} (Score: {final_score}). "
        summary += f"Fundamental ({fund_section.status}), Teknikal ({tech_section.status}), Sentimen ({sent_section.status}). "
        if fund_section.score > 70: summary += "Faktor pendorong utama adalah valuasi yang sangat murah. "
        if tech_section.score < 40: summary += "Waspada tren teknikal yang masih melemah."

        return FullAnalysisResponse(
            stock_code=stock_code,
            company_name=company_name,
            current_price=round(current_price, 2),
            recommendation=recommendation,
            final_score=final_score,
            fundamental=fund_section,
            technical=tech_section,
            sentiment=sent_section,
            summary_rationale=summary,
            last_updated=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in analyze_stock_full for {stock_code}: {error_msg}", exc_info=True)
        
        # Categorize the error for the user
        if "Could not resolve host" in error_msg or "connection" in error_msg.lower():
            friendly_msg = f"Koneksi ke data source (Yahoo Finance) gagal. Pastikan internet Anda aktif atau coba lagi nanti. Error: {error_msg}"
        elif "No data found" in error_msg:
            friendly_msg = f"Data untuk saham {stock_code} tidak ditemukan di Yahoo Finance."
        else:
            friendly_msg = f"Terjadi kesalahan saat menganalisis saham: {error_msg}"
            
        raise HTTPException(status_code=500, detail=friendly_msg)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_DEBUG,
        workers=1
    )