"""
Sentiment analysis service using IndoBERT
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pandas as pd
import numpy as np
from typing import List, Dict, Union, Optional
from scipy.special import softmax
from functools import lru_cache

from config import SENTIMENT_MODEL, MAX_SEQUENCE_LENGTH
from utils.preprocessing import text_preprocessor

class SentimentAnalyzer:
    """Sentiment analysis using IndoBERT model"""
    
    def __init__(self):
        """Initialize IndoBERT sentiment model"""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")
        
        try:
            # Load model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
            self.model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
            self.model.to(self.device)
            self.model.eval()
            print("IndoBERT model loaded successfully")
        except Exception as e:
            print(f"Error loading IndoBERT model: {str(e)}")
            print("Falling back to rule-based sentiment analysis")
            self.model = None
            self.tokenizer = None
    
    @lru_cache(maxsize=1000)
    def predict_sentiment_bert_cached(self, text: str) -> Dict[str, float]:
        """Cached version of BERT sentiment prediction"""
        # We wrap it here because lru_cache on a method includes 'self' in the key
        # which can be problematic if the object state changes, but here it's fine.
        return self.predict_sentiment_bert(text)

    def predict_sentiment_bert(self, text: str) -> Dict[str, float]:
        """
        Predict sentiment using IndoBERT
        
        Args:
            text: Input text string
        
        Returns:
            Dictionary with sentiment scores
        """
        if self.model is None or self.tokenizer is None:
            return self._rule_based_sentiment(text)
        
        try:
            # Preprocess text
            processed_text = text_preprocessor.preprocess(text, remove_stopwords_flag=False)
            
            # Tokenize
            inputs = self.tokenizer(
                processed_text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_SEQUENCE_LENGTH,
                padding=True
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = softmax(logits.cpu().numpy(), axis=1)
            
            # Map to sentiment (assuming 0=negative, 1=neutral, 2=positive)
            # Adjust based on actual model configuration
            sentiment_map = ['negative', 'neutral', 'positive']
            
            result = {}
            for i, sent in enumerate(sentiment_map):
                result[sent] = float(probabilities[0][i])
            
            # Calculate sentiment score (-1 to 1)
            sentiment_score = (
                -1 * result['negative'] +
                0 * result['neutral'] +
                1 * result['positive']
            )
            result['score'] = sentiment_score
            
            return result
            
        except Exception as e:
            print(f"Error in BERT sentiment prediction: {str(e)}")
            return self._rule_based_sentiment(text)
    
    def _rule_based_sentiment(self, text: str) -> Dict[str, float]:
        """
        Fallback rule-based sentiment analysis
        
        Args:
            text: Input text string
        
        Returns:
            Dictionary with sentiment scores
        """
        text_lower = text.lower()
        
        # Positive keywords (Indonesian)
        positive_words = {
            'positif', 'naik', 'meningkat', 'pertumbuhan', 'laba', 'keuntungan',
            'rekomendasi', 'beli', 'buy', 'target', 'cerah', 'ekspansi', 'sukses'
        }
        
        # Negative keywords
        negative_words = {
            'negatif', 'turun', 'menurun', 'rugi', 'kerugian', 'penurunan',
            'jual', 'sell', 'waspada', 'risiko', 'krisis', 'masalah'
        }
        
        # Count sentiment words
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        total = pos_count + neg_count
        
        if total == 0:
            sentiment_score = 0
            pos_prob = 0.33
            neg_prob = 0.33
            neu_prob = 0.34
        else:
            sentiment_score = (pos_count - neg_count) / total
            pos_prob = pos_count / total if total > 0 else 0.33
            neg_prob = neg_count / total if total > 0 else 0.33
            neu_prob = 1 - (pos_prob + neg_prob)
        
        return {
            'positive': pos_prob,
            'neutral': neu_prob,
            'negative': neg_prob,
            'score': sentiment_score
        }
    
    def analyze_news_batch(self, news_articles: List[Dict]) -> pd.DataFrame:
        """
        Analyze sentiment for a batch of news articles
        
        Args:
            news_articles: List of news article dictionaries
        
        Returns:
            DataFrame with sentiment analysis results
        """
        results = []
        
        for article in news_articles:
            # Combine title and content for analysis
            full_text = f"{article.get('title', '')} {article.get('content', '')}"
            
            if full_text.strip():
                sentiment = self.predict_sentiment_bert(full_text)
                results.append({
                    'date': article.get('date'),
                    'title': article.get('title'),
                    'sentiment_score': sentiment['score'],
                    'sentiment_positive': sentiment['positive'],
                    'sentiment_neutral': sentiment['neutral'],
                    'sentiment_negative': sentiment['negative']
                })
        
        return pd.DataFrame(results)
    
    def get_daily_sentiment_score(self, df_sentiment: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate sentiment scores by date
        
        Args:
            df_sentiment: DataFrame with sentiment analysis results
        
        Returns:
            DataFrame with daily aggregated sentiment scores
        """
        if df_sentiment.empty:
            return pd.DataFrame()
        
        # Convert date column to datetime (timezone-naive)
        df_sentiment['date'] = pd.to_datetime(df_sentiment['date']).dt.tz_localize(None)
        
        # Aggregate by date
        daily_sentiment = df_sentiment.groupby('date').agg({
            'sentiment_score': 'mean',
            'sentiment_positive': 'mean',
            'sentiment_neutral': 'mean',
            'sentiment_negative': 'mean'
        }).reset_index()
        
        return daily_sentiment

# Global instance
sentiment_analyzer = SentimentAnalyzer()