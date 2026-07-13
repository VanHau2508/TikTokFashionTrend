import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging
import re

logger = logging.getLogger(__name__)

class NLPAnalyzer:
    """PhoBERT Sentiment Analysis - Trained Model"""
    
    def __init__(self, model_path='ai/models/phobert_sentiment_model_final'):
        logger.info(f"Loading trained PhoBERT from: {model_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()
        
        self.sentiment_map = {0: 'negative', 1: 'neutral', 2: 'positive'}
        
        logger.info(f"✅ PhoBERT loaded! Device: {self.device}")
    
    def analyze_text(self, text, max_length=128):
        """Analyze sentiment"""
        
        if not text or len(text.strip()) == 0:
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'pred_class': 1
            }
        
        try:
            inputs = self.tokenizer(
                text,
                return_tensors='pt',
                truncation=True,
                max_length=max_length
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=1)
                pred_class = torch.argmax(probs, dim=1).item()
                confidence = probs[0][pred_class].item()
            
            return {
                'sentiment': self.sentiment_map.get(pred_class, 'neutral'),
                'confidence': round(float(confidence), 4),
                'pred_class': int(pred_class)
            }
            
        except Exception as e:
            logger.error(f"Error: {e}")
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'pred_class': 1
            }
        
    def _extract_hashtags(self, text):
        """
        Trích xuất danh sách hashtag từ chuỗi văn bản.
        Ví dụ: "#fashion #thoitrang" -> ["#fashion", "#thoitrang"]
        """
        if not text:
            return []
        # Regex này bắt được các hashtag có chứa chữ cái (bao gồm tiếng Việt) và số
        return re.findall(r'#\w+', text)