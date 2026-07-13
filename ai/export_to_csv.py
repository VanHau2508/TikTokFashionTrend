import pandas as pd
import logging
from database.config import SessionLocal
from database.models import Comment
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_comments_csv():
    """Export comments từ PostgreSQL sang CSV"""
    
    logger.info(f"\n{'='*70}")
    logger.info(f"📊 EXPORTING COMMENTS FROM DATABASE")
    logger.info(f"{'='*70}\n")
    
    db = SessionLocal()
    
    try:
        # Query all comments
        comments = db.query(Comment).all()
        
        logger.info(f"📝 Total comments in DB: {len(comments)}")
        
        if len(comments) == 0:
            logger.error("❌ No comments found!")
            return False
        
        # Convert to list of dicts
        data = []
        for c in comments:
            data.append({
                'comment_id': c.comment_id,
                'video_id': c.video_id,
                'content': c.content,
                'sentiment': c.sentiment if c.sentiment else 'unknown',
                'like_count': c.like_count,
                'created_date': c.created_date.isoformat() if c.created_date else ''
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        logger.info(f"✅ Loaded {len(df)} rows")
        
        # Remove duplicates by content
        df_original_count = len(df)
        df = df.drop_duplicates(subset=['content'], keep='first')
        df_after_dedup = len(df)
        
        logger.info(f"📋 After removing duplicates: {df_after_dedup} rows")
        logger.info(f"   (Removed {df_original_count - df_after_dedup} duplicates)")
        
        # Create output directory
        import os
        os.makedirs('ai/training_data', exist_ok=True)
        
        # Save to CSV
        output_file = 'ai/training_data/tiktok_comments_dataset.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        logger.info(f"\n✅ EXPORT COMPLETE!")
        logger.info(f"📁 File: {output_file}")
        logger.info(f"📊 Rows: {len(df)}")
        logger.info(f"\n📊 DISTRIBUTION:")
        
        # Show sentiment distribution
        sentiment_dist = df['sentiment'].value_counts()
        for sentiment, count in sentiment_dist.items():
            percentage = (count / len(df)) * 100
            logger.info(f"   {sentiment:10s}: {count:5d} ({percentage:5.1f}%)")
        
        logger.info(f"\n📋 SAMPLE DATA:")
        logger.info(df[['content', 'sentiment']].head(5).to_string())
        
        logger.info(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    export_comments_csv()