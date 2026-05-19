"""
Text preprocessing utilities for sentiment analysis
"""

import re
import nltk
from nltk.corpus import stopwords
from typing import List, Optional

# Download NLTK data automatically with error handling
def download_nltk_resources():
    """Download required NLTK resources"""
    resources = ['punkt', 'stopwords']
    for resource in resources:
        try:
            nltk.data.find(f'tokenizers/{resource}')
        except LookupError:
            try:
                nltk.download(resource, quiet=False)
                print(f"Downloaded NLTK resource: {resource}")
            except Exception as e:
                print(f"Warning: Could not download {resource}: {e}")
        
        # Special handling for stopwords
        if resource == 'stopwords':
            try:
                nltk.data.find('corpora/stopwords')
            except LookupError:
                try:
                    nltk.download('stopwords', quiet=False)
                    print("Downloaded NLTK stopwords")
                except Exception as e:
                    print(f"Warning: Could not download stopwords: {e}")

# Download resources when module loads
download_nltk_resources()

class TextPreprocessor:
    """Text preprocessing class for Indonesian text"""
    
    def __init__(self):
        """Initialize preprocessor with Indonesian stopwords"""
        try:
            self.stop_words = set(stopwords.words('indonesian'))
        except:
            # Fallback stopwords if NLTK fails
            self.stop_words = self._get_fallback_stopwords()
            print("Using fallback Indonesian stopwords")
        
        # Add custom financial stopwords
        self.custom_stopwords = {
            'saham', 'harga', 'pasar', 'investor', 'perusahaan',
            'bisnis', 'ekonomi', 'keuangan', 'analis', 'rekomendasi'
        }
        self.stop_words.update(self.custom_stopwords)
    
    def _get_fallback_stopwords(self):
        """Provide fallback Indonesian stopwords"""
        return {
            'yang', 'dan', 'di', 'dari', 'ini', 'itu', 'adalah', 'untuk',
            'dengan', 'pada', 'akan', 'juga', 'dalam', 'dia', 'mereka',
            'kita', 'kami', 'anda', 'saya', 'kamu', 'kepada', 'oleh',
            'sebagai', 'atau', 'jika', 'maka', 'tetapi', 'namun', 'karena',
            'setelah', 'sebelum', 'sudah', 'belum', 'lagi', 'masih',
            'selalu', 'pernah', 'sedang', 'sangat', 'begitu', 'begini',
            'begitu', 'sekali', 'saja', 'pun', 'bisa', 'dapat', 'harus'
        }
    
    def lowercase(self, text: str) -> str:
        """Convert text to lowercase"""
        return text.lower() if text else ""
    
    def remove_symbols(self, text: str) -> str:
        """Remove special symbols and punctuation"""
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        # Remove mentions and hashtags
        text = re.sub(r'@\w+|#\w+', '', text)
        # Remove numbers (optional - keep if needed for context)
        text = re.sub(r'\d+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra whitespaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def remove_stopwords(self, text: str) -> str:
        """Remove Indonesian stopwords"""
        words = text.split()
        words = [w for w in words if w not in self.stop_words]
        return ' '.join(words)
    
    def preprocess(self, text: str, remove_stopwords_flag: bool = True) -> str:
        """
        Complete preprocessing pipeline
        
        Args:
            text: Input text string
            remove_stopwords_flag: Whether to remove stopwords
        
        Returns:
            Preprocessed text
        """
        if not text:
            return ""
        
        text = self.lowercase(text)
        text = self.remove_symbols(text)
        if remove_stopwords_flag:
            text = self.remove_stopwords(text)
        
        return text
    
    def preprocess_batch(self, texts: List[str], remove_stopwords_flag: bool = True) -> List[str]:
        """Preprocess a batch of texts"""
        return [self.preprocess(t, remove_stopwords_flag) for t in texts]

# Global instance
text_preprocessor = TextPreprocessor()