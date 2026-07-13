"""
Batch NLP Processing - Save results to DB
"""

import logging
import json
from datetime import datetime, timezone
from database.config import SessionLocal
from database.models import Video, Comment, AIAnalysis, AIModel
from ai.nlp_analyzer import NLPAnalyzer
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BatchNLPProcessorFinal:
    """Batch process all videos with NLP + save to DB"""
    
    def __init__(self, model_path='ai/models/phobert_sentiment_model_final'):
        logger.info("Initializing NLP batch processor...")
        
        self.db = SessionLocal()
        self.analyzer = NLPAnalyzer(model_path)
        self.model_id = 1  # PhoBERT
        
        logger.info("✅ Ready!\n")
    
    def process_videos(self, limit=None, batch_size=50):
        """Process unanalyzed videos"""
        
        logger.info("="*70)
        logger.info("🧠 BATCH NLP PROCESSING - VIDEOS")
        logger.info("="*70 + "\n")
        
        try:
            # Get unanalyzed videos
            query = self.db.query(Video).filter(Video.is_analyzed == False)
            
            if limit:
                query = query.limit(limit)
            
            videos = query.all()
            
            if not videos:
                logger.warning("No unanalyzed videos found!")
                return 0
            
            logger.info(f"📹 Found {len(videos)} unanalyzed videos\n")
            
            processed = 0
            
            for idx, video in enumerate(videos, 1):
                try:
                    if not video.description:
                        continue
                    
                    # Analyze
                    nlp_result = self.analyzer.analyze_text(video.description)
                    
                    # Extract keywords
                    keywords = self.analyzer._extract_hashtags(video.description)
                    
                    # Save to ai_analysis
                    analysis_data = {
                        'sentiment': nlp_result['sentiment'],
                        'confidence': nlp_result['confidence'],
                        'keywords': keywords,
                    }
                    
                    analysis = AIAnalysis(
                        video_id=video.video_id,
                        model_id=self.model_id,
                        analysis_type='nlp',
                        result_json=json.dumps(analysis_data, ensure_ascii=False),
                        confidence_score=nlp_result['confidence']
                    )
                    
                    self.db.add(analysis)
                    
                    # Update video
                    video.is_analyzed = True
                    
                    self.db.commit()
                    processed += 1
                    
                    if idx % batch_size == 0 or idx == len(videos):
                        logger.info(f"✅ Processed {idx}/{len(videos)} videos")
                    
                except Exception as e:
                    logger.error(f"Error: {e}")
                    self.db.rollback()
            
            logger.info(f"\n{'='*70}")
            logger.info(f"✅ VIDEOS PROCESSED: {processed}")
            logger.info(f"{'='*70}\n")
            
            return processed
        
        finally:
            self.db.close()
    
    def process_comments(self, batch_size=300):
        """Process all comments with sentiment"""
        
        logger.info("="*70)
        logger.info("💬 BATCH NLP PROCESSING - COMMENTS")
        logger.info("="*70 + "\n")
        
        try:
            self.db = SessionLocal()
            
            # Get comments without sentiment
            comments = self.db.query(Comment).filter(
                Comment.sentiment == None
            ).all()
            
            if not comments:
                logger.warning("No comments to process!")
                return 0
            
            logger.info(f"💬 Found {len(comments)} unanalyzed comments\n")
            
            processed = 0
            
            for idx, comment in enumerate(comments, 1):
                try:
                    if not comment.content:
                        continue
                    
                    # Analyze
                    result = self.analyzer.analyze_text(comment.content)
                    
                    # Update
                    comment.sentiment = result['sentiment']
                    
                    self.db.commit()
                    processed += 1
                    
                    if idx % batch_size == 0 or idx == len(comments):
                        logger.info(f"✅ Processed {idx}/{len(comments)} comments")
                    
                except Exception as e:
                    logger.error(f"Error: {e}")
                    self.db.rollback()
            
            logger.info(f"\n{'='*70}")
            logger.info(f"✅ COMMENTS PROCESSED: {processed}")
            logger.info(f"{'='*70}\n")
            
            return processed
        
        finally:
            self.db.close()

def main():
    processor = BatchNLPProcessorFinal()
    
    # Process videos
    videos_processed = processor.process_videos(limit=None, batch_size=100)
    
    # Process comments
    comments_processed = processor.process_comments(batch_size=500)
    
    logger.info("\n" + "="*70)
    logger.info("📊 FINAL SUMMARY")
    logger.info("="*70)
    logger.info(f"   Videos processed: {videos_processed}")
    logger.info(f"   Comments processed: {comments_processed}")
    logger.info("="*70 + "\n")

if __name__ == "__main__":
    main()