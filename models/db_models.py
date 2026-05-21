from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON, func
from api.database import Base

class StockPriceRealtime(Base):
    """Stores current prices of LQ45 stocks for the landing page"""
    __tablename__ = 'stock_prices_realtime'

    stock_code = Column(String(20), primary_key=True)
    company_name = Column(String(100), nullable=False)
    current_price = Column(Float, default=0.0)
    prev_close = Column(Float, default=0.0)
    daily_change = Column(Float, default=0.0)
    daily_change_pct = Column(Float, default=0.0)
    volume = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class Screening(Base):
    """Stores full ML and fundamental screening results for trained stocks"""
    __tablename__ = 'screenings'

    stock_code = Column(String(20), primary_key=True)
    company_name = Column(String(100), nullable=False)
    current_price = Column(Float, default=0.0)
    fair_value = Column(Float, nullable=True)
    upside_potential = Column(Float, nullable=True)
    
    # Margin of safety
    mos_percentage = Column(Float, nullable=True)
    mos_level = Column(String(50), default='N/A')
    mos_action = Column(String(100), default='N/A')
    
    # Validation status & weights
    valuation_status = Column(String(50), default='INVALID')
    valuation_methods_used = Column(JSON, nullable=True)  # JSON field to store list
    valuation_method_weights = Column(JSON, nullable=True)  # JSON field to store dict
    
    # Core scores
    recommendation = Column(String(50), default='NEUTRAL')
    final_score = Column(Float, default=50.0)
    fundamental_score = Column(Float, default=50.0)
    technical_score = Column(Float, default=50.0)
    sentiment_score = Column(Float, default=50.0)
    
    # Sentiment details
    sentiment_label = Column(String(50), default='Neutral')
    news_analyzed = Column(Integer, default=0)
    
    # Raw calculation data (for transparency)
    fund_roe = Column(Float, nullable=True)
    fund_per = Column(Float, nullable=True)
    fund_der = Column(Float, nullable=True)
    fund_eps = Column(Float, nullable=True)
    fund_dividend = Column(Float, nullable=True)
    
    tech_rsi = Column(Float, nullable=True)
    tech_macd = Column(Float, nullable=True)
    tech_ma20 = Column(Float, nullable=True)
    tech_ma50 = Column(Float, nullable=True)
    
    # Quality filter
    quality_passed = Column(Boolean, default=True)
    quality_reasons = Column(JSON, nullable=True)
    
    # Qualitative summary
    summary_rationale = Column(Text, nullable=True)
    
    # Status
    is_trained = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class NewsSentiment(Base):
    """Stores detailed sentiment logs for news items of a stock"""
    __tablename__ = 'news_sentiments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    date = Column(String(100), nullable=True)
    source = Column(String(100), default='Unknown')
    url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    sentiment_score = Column(Float, default=0.0)
    sentiment_label = Column(String(50), default='Neutral')
    created_at = Column(DateTime, default=func.now())
