import logging
import asyncio
import re
import xml.etree.ElementTree as ET
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dateutil import parser
from typing import Dict, List, Optional, Tuple, Any

from api.database import SessionLocal
from models.db_models import Screening, NewsSentiment, StockPriceRealtime
from services.data_collector import DataCollector
from services.feature_engineering import FeatureEngineer
from services.sentiment_analysis import sentiment_analyzer
from services.ml_model import stock_predictor
from services.fundamental_analysis import fundamental_analyzer
from config.constants import COMPANY_NAMES, NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS
from utils.helpers import convert_to_native

logger = logging.getLogger(__name__)

# Initialize services
data_collector = DataCollector()
feature_engineer = FeatureEngineer()
# http_client removed from global scope

# Semaphores for concurrency control removed from global scope

def get_company_name(stock_code: str) -> str:
    return COMPANY_NAMES.get(stock_code, stock_code.replace('.JK', ''))

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
    
    pos_count = sum(1 for m in matched_keywords if m[2] == 'positive')
    neg_count = sum(1 for m in matched_keywords if m[2] == 'negative')
    
    if pos_count >= 2: score *= 1.3
    if neg_count >= 2: score *= 1.3
    
    score = max(-1, min(1, score))
    return score, matched_keywords

def combine_sentiment_scores(bert_score: float, rule_score: float, text: str = "") -> float:
    if abs(rule_score) > 0.15:
        if bert_score * rule_score > 0:
            final_score = (rule_score * 0.8 + bert_score * 0.2) * 1.3
        else:
            final_score = rule_score * 0.7 + bert_score * 0.3
    else:
        if abs(bert_score) > 0.3:
            final_score = bert_score * 0.7 + rule_score * 0.3
        else:
            final_score = bert_score * 0.5 + rule_score * 0.5
            
    return max(-1, min(1, final_score))

async def analyze_single_article(item: Any) -> Optional[Dict]:
    try:
        title = item.find('title').text if item.find('title') is not None else ""
        description = item.find('description').text if item.find('description') is not None else ""
        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
        link = item.find('link').text if item.find('link') is not None else ""
        source = item.find('source').text if item.find('source') is not None else "Google News"
        
        description = re.sub(r'<[^>]+>', '', description)
        full_text = f"{title}. {description}"
        
        # Analyze sentiment using IndoBERT
        # Fallback will run inside the predictor if model is not loaded
        loop = asyncio.get_event_loop()
        bert_result = await loop.run_in_executor(
            None, sentiment_analyzer.predict_sentiment_bert_cached, full_text
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
        
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
        
        if response.status_code != 200:
            return 0.5, 0, "Neutral", []
            
        root = ET.fromstring(response.text)
        items = root.findall('.//item')[:30]
        
        if not items:
            return 0.5, 0, "Neutral", []
            
        sentiment_semaphore = asyncio.Semaphore(1)
        async def sem_analyze(item):
            async with sentiment_semaphore:
                return await analyze_single_article(item)
                
        tasks = [sem_analyze(item) for item in items]
        results = await asyncio.gather(*tasks)
        
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
    except Exception as e:
        logger.error(f"Error fetching news for {stock_code}: {e}")
        return 0.5, 0, "Neutral", []

def calculate_final_score(fund_score: Optional[float], tech_score: Optional[float], sent_score: Optional[float]) -> float:
    fund_score = fund_score if fund_score is not None else 50.0
    tech_score = tech_score if tech_score is not None else 50.0
    sent_score = sent_score if sent_score is not None else 0.5
    
    f = fund_score / 100 if fund_score > 1 else fund_score
    t = tech_score / 100 if tech_score > 1 else tech_score
    s = sent_score
    
    final = (0.5 * f) + (0.3 * t) + (0.2 * s)
    return round(float(final * 100), 1)  # Scale to 0-100 for display

def get_recommendation(final_score: float) -> str:
    # Scale back to 0-1 for recommendation checks if final_score is 0-100
    score = final_score / 100 if final_score > 1 else final_score
    if score >= 0.75:
        return "STRONG BUY"
    elif score >= 0.60:
        return "ACCUMULATE"
    elif score >= 0.45:
        return "HOLD"
    elif score >= 0.30:
        return "REDUCE"
    else:
        return "SELL"

async def run_screening_and_save(stock_code: str, db) -> Dict[str, Any]:
    """
    Core engine that gathers technical, sentiment, and fundamental data,
    predicts using trained models, and stores results to MySQL.
    """
    logger.info(f"Running screening compilation for {stock_code}...")
    
    if not stock_code.endswith('.JK'):
        stock_code = f"{stock_code}.JK"
        
    company_name = get_company_name(stock_code)
    
    # 1. Fetch current price
    ticker = yf.Ticker(stock_code)
    df_hist = await asyncio.get_event_loop().run_in_executor(
        None, lambda: ticker.history(period="1y")
    )
    
    if df_hist.empty:
        raise ValueError(f"No price history found for {stock_code}")
        
    latest_row = df_hist.iloc[-1]
    current_price = float(latest_row['Close'])
    
    # Calculate daily change
    prev_close = float(df_hist.iloc[-2]['Close']) if len(df_hist) > 1 else current_price
    daily_change = current_price - prev_close
    daily_change_pct = (daily_change / prev_close * 100) if prev_close != 0 else 0.0
    volume = float(latest_row['Volume'])
    
    # Update real-time price in DB
    db_price = db.query(StockPriceRealtime).filter(StockPriceRealtime.stock_code == stock_code).first()
    if not db_price:
        db_price = StockPriceRealtime(stock_code=stock_code, company_name=company_name)
        db.add(db_price)
    db_price.current_price = current_price
    db_price.prev_close = prev_close
    db_price.daily_change = daily_change
    db_price.daily_change_pct = daily_change_pct
    db_price.volume = volume
    db_price.last_updated = datetime.now()
    
    # 2. News Sentiment
    sentiment_score, news_count, sentiment_label, news_items = await fetch_news_with_details(stock_code)
    
    # Save/Update News Sentiments in DB
    db.query(NewsSentiment).filter(NewsSentiment.stock_code == stock_code).delete()
    for item in news_items:
        db_news = NewsSentiment(
            stock_code=stock_code,
            title=item['title'],
            date=item['date'],
            source=item['source'],
            url=item['url'],
            description=item['description'],
            sentiment_score=item['sentiment_score'],
            sentiment_label=item['sentiment_label']
        )
        db.add(db_news)
        
    # 3. Fundamental Analysis
    loop = asyncio.get_event_loop()
    fund_data = await loop.run_in_executor(
        None, fundamental_analyzer.get_complete_fundamental_data, stock_code
    )
    if 'error' in fund_data:
        raise ValueError(f"Fundamental analysis failed: {fund_data['error']}")
        
    fund_safe = convert_to_native(fund_data)
    fund_score = float(fund_safe.get('fundamental_recommendation', {}).get('score', 50))
    
    # 4. Technical analysis (ML Model Prediction)
    tech_score = 50.0
    predicted_return = 0.0
    
    # Load model on-demand
    model_dir = "models/saved_models"
    import joblib
    import os
    ticker_clean = stock_code.replace('.JK', '')
    model_path = os.path.join(model_dir, f"random_forest_{stock_code}.pkl")
    scaler_path = os.path.join(model_dir, f"scaler_{stock_code}.pkl")
    
    if os.path.exists(model_path):
        try:
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None
            
            # Pass ticker_clean so feature extraction uses time-aware fundamentals
            # (matches what was used during training — avoids mismatch)
            features = await loop.run_in_executor(
                None, lambda: get_features_cached_local(stock_code, sentiment_score, ticker_clean)
            )
            
            if features is not None:
                features_scaled = scaler.transform(features) if scaler else features

                # Use predict_proba (BUY probability 0.0–1.0) → scale to 0–100
                # This is far more informative than hard 0/1 prediction
                if hasattr(model, 'predict_proba'):
                    buy_proba = float(model.predict_proba(features_scaled)[0, 1])
                else:
                    buy_proba = float(model.predict(features_scaled)[0])

                tech_score = round(buy_proba * 100, 1)
                logger.info(f"ML BUY probability for {stock_code}: {buy_proba:.3f} → tech_score={tech_score}")
        except Exception as e:
            logger.warning(f"Error making ML prediction for {stock_code} screening: {e}")
            
    # Always calculate tech metrics for database transparency
    if not df_hist.empty:
        df_tech = feature_engineer.calculate_technical_features(df_hist)
        latest_tech = df_tech.dropna(subset=['ma20', 'rsi']).iloc[-1] if not df_tech.dropna(subset=['ma20', 'rsi']).empty else df_tech.iloc[-1]
        rsi = float(latest_tech['rsi']) if 'rsi' in latest_tech and not pd.isna(latest_tech['rsi']) else 50.0
        macd = float(latest_tech['macd_hist']) if 'macd_hist' in latest_tech and not pd.isna(latest_tech['macd_hist']) else 0.0
        ma20 = float(latest_tech['ma20']) if 'ma20' in latest_tech and not pd.isna(latest_tech['ma20']) else current_price
        ma50 = float(latest_tech['ma50']) if 'ma50' in latest_tech and not pd.isna(latest_tech['ma50']) else current_price
    else:
        rsi = 50.0; macd = 0.0; ma20 = current_price; ma50 = current_price

    # If ML prediction failed/not trained, fallback to simple rolling technical indicator score
    if tech_score == 50.0 and not df_hist.empty:
        t_score = 50
        if current_price > ma20 and ma20 > ma50: t_score += 20
        if rsi < 30: t_score += 15
        if rsi > 70: t_score -= 15
        if macd > 0: t_score += 10
        tech_score = float(max(0, min(100, t_score)))
        
    # 5. Final scores
    final_score = calculate_final_score(fund_score, tech_score, sentiment_score)
    recommendation = get_recommendation(final_score)
    
    # 6. Rationale Summary Compilation
    summary = f"Rekomendasi {recommendation} (Score: {final_score}). "
    summary += f"Fundamental: {fund_safe.get('fundamental_recommendation', {}).get('label', 'Neutral')}, "
    summary += f"Teknikal: { 'Positive' if tech_score > 60 else 'Negative' if tech_score < 40 else 'Neutral' }, "
    summary += f"Sentimen: {sentiment_label}. "
    if fund_score > 70:
        summary += f"Faktor pendorong utama adalah valuasi harga wajar Rp{fund_safe.get('fair_value')}."
        
    # 7. Save/Update Screening in DB
    db_screen = db.query(Screening).filter(Screening.stock_code == stock_code).first()
    if not db_screen:
        db_screen = Screening(stock_code=stock_code, company_name=company_name)
        db.add(db_screen)
        
    db_screen.current_price = current_price
    db_screen.fair_value = fund_safe.get('fair_value')
    db_screen.upside_potential = fund_safe.get('upside_potential')
    
    mos = fund_safe.get('margin_of_safety', {})
    db_screen.mos_percentage = mos.get('percentage')
    db_screen.mos_level = mos.get('level', 'N/A')
    db_screen.mos_action = mos.get('action', 'N/A')
    
    db_screen.valuation_status = fund_safe.get('valuation_status', 'INVALID')
    db_screen.valuation_methods_used = fund_safe.get('valuation_methods_used', [])
    db_screen.valuation_method_weights = fund_safe.get('valuation_method_weights', {})
    
    db_screen.recommendation = recommendation
    db_screen.final_score = final_score
    db_screen.fundamental_score = fund_score
    db_screen.technical_score = tech_score
    db_screen.sentiment_score = round(float(sentiment_score * 100), 1)
    db_screen.sentiment_label = sentiment_label
    db_screen.news_analyzed = news_count
    
    # Save raw calculation details
    fundamental_raw = data_collector.get_fundamental_data(stock_code)
    db_screen.fund_roe = fundamental_raw.get('roe')
    db_screen.fund_per = fundamental_raw.get('per')
    db_screen.fund_der = fundamental_raw.get('der')
    db_screen.fund_eps = fundamental_raw.get('eps')
    db_screen.fund_dividend = fundamental_raw.get('dividend')
    db_screen.tech_rsi = rsi
    db_screen.tech_macd = macd
    db_screen.tech_ma20 = ma20
    db_screen.tech_ma50 = ma50
    
    quality = fund_safe.get('quality_check', {})
    db_screen.quality_passed = quality.get('passed', True)
    db_screen.quality_reasons = quality.get('reasons', [])
    
    db_screen.summary_rationale = summary
    db_screen.is_trained = True
    db_screen.last_updated = datetime.now()
    
    db.commit()
    logger.info(f"Screening data for {stock_code} successfully saved to MySQL.")
    
    return {
        'stock_code': stock_code,
        'company_name': company_name,
        'current_price': current_price,
        'recommendation': recommendation,
        'final_score': final_score,
        'is_trained': True
    }

def get_features_cached_local(
    stock_code: str,
    sentiment_score: float,
    ticker_clean: str = None
) -> Optional[np.ndarray]:
    """
    Helper to run feature extraction for real-time ML prediction.
    ticker_clean must be passed so create_complete_dataset can perform
    time-aware fundamental merge — identical to what was done during training.
    """
    try:
        ticker_clean = ticker_clean or stock_code.replace('.JK', '')
        t = yf.Ticker(stock_code)
        df = t.history(period="1y")
        if df.empty or len(df) < 50:
            return None
            
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        fundamental = data_collector.get_fundamental_data(stock_code)
        
        dates = pd.to_datetime(df['Date'])
        sentiment_df = pd.DataFrame({
            'date': dates,
            'sentiment_score': sentiment_score,
            'sentiment_positive': max(0, sentiment_score),
            'sentiment_neutral': 1 - abs(sentiment_score),
            'sentiment_negative': max(0, -sentiment_score)
        })
        
        # Pass ticker_clean → enables time-aware fundamental merge
        df_complete = feature_engineer.create_complete_dataset(
            df, fundamental, sentiment_df, ticker_clean=ticker_clean
        )
        if df_complete.empty:
            return None
            
        X, _, _ = feature_engineer.prepare_features_for_model(df_complete)
        if len(X) == 0:
            return None
            
        return X[-1:].reshape(1, -1)
    except Exception as e:
        logger.error(f"Local features extraction failed for {stock_code}: {e}")
        return None
