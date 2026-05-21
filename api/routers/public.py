import logging
import asyncio
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from api.database import get_db
from models.db_models import StockPriceRealtime, Screening, NewsSentiment
from config import LQ45_STOCKS
from config.constants import COMPANY_NAMES

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/public",
    tags=["Public API"]
)

def get_company_name(stock_code: str) -> str:
    return COMPANY_NAMES.get(stock_code, stock_code.replace('.JK', ''))

async def update_cached_prices(db: Session):
    """Download prices for all LQ45 stocks in bulk and update the MySQL cache"""
    try:
        logger.info("Starting bulk refresh of stock prices from Yahoo Finance...")
        loop = asyncio.get_event_loop()
        
        # Download in bulk - very fast (1-2 seconds)
        df_bulk = await loop.run_in_executor(
            None, 
            lambda: yf.download(
                tickers=LQ45_STOCKS, 
                period="5d", 
                interval="1d", 
                group_by='ticker',
                progress=False
            )
        )
        
        if df_bulk.empty:
            logger.warning("Bulk download returned empty DataFrame")
            return
            
        for code in LQ45_STOCKS:
            try:
                # Handle single vs multi-ticker dataframe shapes
                if len(LQ45_STOCKS) > 1:
                    if code not in df_bulk.columns.levels[0]:
                        continue
                    df_ticker = df_bulk[code].dropna(subset=['Close'])
                else:
                    df_ticker = df_bulk.dropna(subset=['Close'])
                    
                if df_ticker.empty or len(df_ticker) < 2:
                    continue
                    
                closes = df_ticker['Close'].values
                volumes = df_ticker['Volume'].values if 'Volume' in df_ticker.columns else [0.0, 0.0]
                
                latest_close = float(closes[-1])
                prev_close = float(closes[-2])
                daily_change = latest_close - prev_close
                daily_change_pct = (daily_change / prev_close * 100) if prev_close != 0 else 0.0
                volume = float(volumes[-1])
                
                # Update in DB
                db_price = db.query(StockPriceRealtime).filter(StockPriceRealtime.stock_code == code).first()
                if not db_price:
                    db_price = StockPriceRealtime(stock_code=code, company_name=get_company_name(code))
                    db.add(db_price)
                
                db_price.current_price = latest_close
                db_price.prev_close = prev_close
                db_price.daily_change = daily_change
                db_price.daily_change_pct = daily_change_pct
                db_price.volume = volume
                db_price.last_updated = datetime.now()
            except Exception as e:
                logger.error(f"Error processing bulk price for {code}: {e}")
                
        db.commit()
        logger.info("Bulk refresh of stock prices completed and saved to MySQL.")
    except Exception as e:
        logger.error(f"Failed to refresh stock prices in bulk: {e}")

@router.get("/realtime")
async def get_realtime_stocks(db: Session = Depends(get_db)):
    """
    Get real-time stock list for landing page.
    Utilizes a MySQL cache. If cache is older than 5 minutes, triggers a bulk update.
    """
    try:
        # Check if any price exists
        sample_price = db.query(StockPriceRealtime).first()
        
        # Trigger update if no cache exists or cache is stale (> 5 minutes)
        should_update = False
        if not sample_price:
            should_update = True
        else:
            time_diff = datetime.now() - sample_price.last_updated
            if time_diff > timedelta(minutes=5):
                should_update = True
                
        if should_update:
            await update_cached_prices(db)
            
        prices = db.query(StockPriceRealtime).all()
        
        # Map to native JSON structures
        result = []
        for p in prices:
            result.append({
                'stock_code': p.stock_code,
                'company_name': p.company_name,
                'current_price': round(p.current_price, 2),
                'prev_close': round(p.prev_close, 2),
                'daily_change': round(p.daily_change, 2),
                'daily_change_pct': round(p.daily_change_pct, 2),
                'volume': p.volume,
                'last_updated': p.last_updated.isoformat()
            })
            
        return result
    except Exception as e:
        logger.error(f"Error in /public/realtime: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stock prices: {str(e)}")

@router.get("/screening")
async def get_screened_stocks(db: Session = Depends(get_db)):
    """
    Get all stocks that have been trained and compiled by the Admin.
    """
    try:
        screenings = db.query(Screening).filter(Screening.is_trained == True).order_by(Screening.final_score.desc()).all()
        
        result = []
        for s in screenings:
            result.append({
                'stock_code': s.stock_code,
                'company_name': s.company_name,
                'current_price': round(s.current_price, 2),
                'fair_value': round(s.fair_value, 2) if s.fair_value else None,
                'upside_potential': round(s.upside_potential, 2) if s.upside_potential else None,
                'margin_of_safety': {
                    'percentage': round(s.mos_percentage, 2) if s.mos_percentage else None,
                    'level': s.mos_level,
                    'action': s.mos_action
                },
                'recommendation': s.recommendation,
                'final_score': s.final_score,
                'fundamental_score': s.fundamental_score,
                'technical_score': s.technical_score,
                'sentiment_score': s.sentiment_score,
                'sentiment_label': s.sentiment_label,
                'news_analyzed': s.news_analyzed,
                'quality_passed': s.quality_passed,
                'raw_metrics': {
                    'roe': round(s.fund_roe, 2) if s.fund_roe is not None else None,
                    'per': round(s.fund_per, 2) if s.fund_per is not None else None,
                    'rsi': round(s.tech_rsi, 2) if s.tech_rsi is not None else None
                },
                'summary_rationale': s.summary_rationale,
                'last_updated': s.last_updated.isoformat()
            })
            
        return result
    except Exception as e:
        logger.error(f"Error in /public/screening: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve screening data")

@router.get("/analyze/{stock_code}")
async def get_stock_analysis_details(stock_code: str, db: Session = Depends(get_db)):
    """
    Get detailed analysis (Fundamental, Technical, Sentiment) for a trained stock from DB.
    """
    if not stock_code.endswith('.JK'):
        stock_code = f"{stock_code}.JK"
        
    try:
        s = db.query(Screening).filter(Screening.stock_code == stock_code).first()
        
        if not s or not s.is_trained:
            raise HTTPException(
                status_code=404, 
                detail=f"Analisis untuk saham {stock_code} belum tersedia. Silakan hubungi Admin untuk melakukan training terlebih dahulu."
            )
            
        # Get latest 3 news items from DB
        news = db.query(NewsSentiment).filter(NewsSentiment.stock_code == stock_code).order_by(NewsSentiment.created_at.desc()).limit(3).all()
        
        response = {
            'stock_code': s.stock_code,
            'company_name': s.company_name,
            'current_price': round(s.current_price, 2),
            'recommendation': s.recommendation,
            'final_score': s.final_score,
            
            'fundamental': {
                'score': s.fundamental_score,
                'status': s.mos_level,
                'raw_metrics': {
                    'roe': round(s.fund_roe, 2) if s.fund_roe is not None else None,
                    'per': round(s.fund_per, 2) if s.fund_per is not None else None,
                    'der': round(s.fund_der, 2) if s.fund_der is not None else None,
                    'eps': round(s.fund_eps, 2) if s.fund_eps is not None else None,
                    'dividend_yield': round(s.fund_dividend, 4) if s.fund_dividend is not None else None
                },
                'details': {
                    'fair_value': round(s.fair_value, 2) if s.fair_value else None,
                    'upside': round(s.upside_potential, 2) if s.upside_potential else None,
                    'valuation_status': s.valuation_status,
                    'valuation_methods_used': s.valuation_methods_used,
                    'valuation_method_weights': s.valuation_method_weights,
                    'quality_passed': s.quality_passed,
                    'quality_reasons': s.quality_reasons
                },
                'rationale': f"Saham {s.company_name} memiliki status valuasi {s.valuation_status} "
                             f"dengan Upside Potential {round(s.upside_potential, 2) if s.upside_potential else 0}%. "
                             f"Hasil pemeriksaan kualitas fundamental: { 'LULUS' if s.quality_passed else 'GAGAL/PERINGATAN' }."
            },
            
            'technical': {
                'score': s.technical_score,
                'status': "Positive" if s.technical_score > 60 else "Negative" if s.technical_score < 40 else "Neutral",
                'raw_indicators': {
                    'rsi': round(s.tech_rsi, 2) if s.tech_rsi is not None else None,
                    'macd': round(s.tech_macd, 4) if s.tech_macd is not None else None,
                    'ma20': round(s.tech_ma20, 2) if s.tech_ma20 is not None else None,
                    'ma50': round(s.tech_ma50, 2) if s.tech_ma50 is not None else None
                },
                'details': {
                    'prediction_trend': "Bullish" if s.technical_score > 60 else "Bearish" if s.technical_score < 40 else "Neutral"
                },
                'rationale': f"Skor teknikal terprediksi AI adalah {s.technical_score}/100. Tren indikasi teknikal jangka menengah menunjukkan sinyal hibrida."
            },
            
            'sentiment': {
                'score': s.sentiment_score,
                'status': s.sentiment_label,
                'details': {
                    'news_analyzed': s.news_analyzed,
                    'top_headlines': [n.title for n in news]
                },
                'rationale': f"Sentimen pasar berlabel {s.sentiment_label} berdasarkan analisis {s.news_analyzed} artikel berita terbaru."
            },
            
            'summary_rationale': s.summary_rationale,
            'last_updated': s.last_updated.isoformat()
        }
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /public/analyze for {stock_code}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
