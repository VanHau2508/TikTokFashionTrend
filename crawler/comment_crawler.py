import logging
from datetime import datetime, timedelta, timezone
import random
from database.config import SessionLocal
from database.models import Video, Comment
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_COMMENTS = [
    'Đẹp lắm! ❤️',
    'Quá xinh, tôi thích lắm',
    'Style tuyệt vời',
    'Phải mua ngay',
    'Giá bao nhiêu vậy?',
    'Chất lượng tốt không?',
    'Gợi ý cho tôi luôn',
    'Yêu thích outfit này',
    'Điểm cộng cho bạn',
    'Tuyệt đẹp!',
    'Phù hợp lắm',
    'Sẽ mua cho vợ',
    'Trending quá',
    'Recommend luôn',
    'Top tier outfit',
]

def seed_comments(num_comments=500):
    """Thêm comments mẫu cho videos"""
    
    logger.info(f"\n{'='*70}")
    logger.info(f"💬 Adding sample comments: {num_comments}")
    logger.info(f"{'='*70}")
    
    db = SessionLocal()
    
    try:
        # Get all videos
        videos = db.query(Video).all()
        logger.info(f"📊 Found {len(videos)} videos")
        
        if not videos:
            logger.warning("⚠️  No videos found!")
            return False
        
        comments_added = 0
        
        for video in videos:
            # Thêm 1-5 comments per video
            num_comments_per_video = random.randint(1, 5)
            
            for _ in range(num_comments_per_video):
                comment_text = random.choice(SAMPLE_COMMENTS)
                commenter_id = f"user_{random.randint(1000, 999999)}"
                
                comment = Comment(
                    video_id=video.video_id,
                    commenter_id=commenter_id,
                    content=comment_text,
                    like_count=random.randint(0, 100),
                    created_date=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 7))
                )
                
                db.add(comment)
                comments_added += 1
                
                if comments_added % 100 == 0:
                    db.commit()
                    logger.info(f"   ✅ Added {comments_added} comments...")
        
        db.commit()
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ Comments added: {comments_added}")
        logger.info(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        db.rollback()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    seed_comments(num_comments=500)